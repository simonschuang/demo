"""
Download API - Agent Installation Package Download
"""
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt

from app.config import settings
from app.database import get_db
from app.auth import get_current_user, get_current_user_optional, verify_token
from app.models.user import User
from app.models.client import Client

router = APIRouter()

# Default releases directory
RELEASES_DIR = Path(os.getenv("RELEASES_DIR", "/app/releases"))

# Install token expiration (24 hours)
INSTALL_TOKEN_EXPIRE_HOURS = 24


def create_install_token(user_id: str) -> str:
    """Create a JWT token for install.sh authentication"""
    expire = datetime.utcnow() + timedelta(hours=INSTALL_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "type": "install",
        "exp": expire
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_install_token(token: str) -> Optional[dict]:
    """Verify install token and return payload"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "install":
            return None
        return payload
    except Exception:
        return None


@router.get("/releases")
async def list_releases(
    current_user: User = Depends(get_current_user)
):
    """List available agent releases"""
    releases = []
    latest_version = None
    
    if RELEASES_DIR.exists():
        # Look for version directories
        for item in sorted(RELEASES_DIR.iterdir(), reverse=True):
            if item.is_dir() and item.name.startswith("v"):
                version = item.name
                releases.append(version)
                if latest_version is None:
                    latest_version = version
        
        # Check for latest symlink
        latest_link = RELEASES_DIR / "latest"
        if latest_link.is_symlink():
            latest_version = latest_link.resolve().name
    
    return {
        "latest": latest_version or "v0.1.0",
        "versions": releases if releases else ["v0.1.0"]
    }


@router.get("/platforms")
async def list_platforms():
    """List supported platforms"""
    return {
        "platforms": [
            {"os": "linux", "arch": "amd64", "label": "Linux (x86_64)"},
            {"os": "linux", "arch": "arm64", "label": "Linux (ARM64)"},
            {"os": "darwin", "arch": "amd64", "label": "macOS (Intel)"},
            {"os": "darwin", "arch": "arm64", "label": "macOS (Apple Silicon)"},
            {"os": "windows", "arch": "amd64", "label": "Windows (x86_64)"}
        ]
    }


@router.get("/install-token")
async def get_install_token(
    current_user: User = Depends(get_current_user)
):
    """Get an install token for use with install.sh"""
    token = create_install_token(str(current_user.id))
    return {
        "token": token,
        "expires_in": INSTALL_TOKEN_EXPIRE_HOURS * 3600,
        "expires_at": (datetime.utcnow() + timedelta(hours=INSTALL_TOKEN_EXPIRE_HOURS)).isoformat()
    }


@router.get("/{version}/{filename}")
async def download_release(
    version: str,
    filename: str,
    token: Optional[str] = Query(None, description="Bearer token for authentication"),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Download a specific release file
    
    Example: GET /download/v1.0.0/install-linux-amd64-v1.0.0.zip?token=xxx
    """
    # Check authentication - either via header or query parameter
    if current_user is None:
        if token:
            # Verify the token from query parameter
            from app.auth import verify_token
            from app.database import async_session_maker
            
            payload = verify_token(token)
            if payload is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
    
    # Validate filename format
    if not filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename format"
        )
    
    # Construct file path
    file_path = RELEASES_DIR / version / filename
    
    # Security check - prevent path traversal
    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(RELEASES_DIR.resolve())):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid path"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path"
        )
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Release file not found: {filename}"
        )
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/zip"
    )


@router.post("/register")
async def register_client_from_install(
    token: str = Query(..., description="Install token from Web UI"),
    hostname: Optional[str] = Query(None, description="Client hostname"),
    db: AsyncSession = Depends(get_db)
):
    """Register a new client from install.sh
    
    This endpoint is called by install.sh to register the client
    and get client_id and client_token for config.yaml
    """
    # Verify install token
    payload = verify_install_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired install token"
        )
    
    user_id = payload.get("sub")
    
    # Create new client
    client = Client(
        hostname=hostname or "unnamed",
        user_id=user_id,
        client_token=secrets.token_urlsafe(32)
    )
    
    db.add(client)
    await db.commit()
    await db.refresh(client)
    
    return {
        "client_id": str(client.id),
        "client_token": client.client_token,
        "server_url": os.getenv("SERVER_URL", "localhost:8080"),
        "ws_scheme": os.getenv("WS_SCHEME", "wss")
    }
