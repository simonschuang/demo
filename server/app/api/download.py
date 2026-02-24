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
from app.auth import get_current_user
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
):
    """Download a specific release file
    
    Example: GET /download/v1.0.0/install-linux-amd64-v1.0.0.zip
    """
    # Validate filename format
    if not (filename.endswith(".zip") or filename.endswith(".tar.gz")):
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
    
    media_type = "application/gzip" if filename.endswith(".tar.gz") else "application/zip"
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type
    )


@router.post("/register")
async def register_client_from_install(
    token: str = Query(..., description="Install token from Web UI or pre-created client token"),
    hostname: Optional[str] = Query(None, description="Client hostname"),
    db: AsyncSession = Depends(get_db)
):
    """Register a new client from install.sh or configure a pre-created client.

    This endpoint is called by config.sh to register the client
    and get client_id and client_token for config.yaml.

    Accepts either:
    - A JWT install token (from /download/install-token)
    - A pre-created client_token (shown on the New Client page)
    """
    # First, check if the token matches a pre-created client
    result = await db.execute(select(Client).where(Client.client_token == token))
    existing_client = result.scalar_one_or_none()

    if existing_client is not None:
        # Update hostname if provided
        if hostname:
            existing_client.hostname = hostname
            await db.commit()
            await db.refresh(existing_client)
        return {
            "client_id": str(existing_client.id),
            "client_token": existing_client.client_token,
            "server_url": os.getenv("SERVER_URL", "localhost:8080"),
            "ws_scheme": os.getenv("WS_SCHEME", "wss")
        }

    # Fall back to JWT install token verification
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
