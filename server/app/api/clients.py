"""
Client API Routes
"""
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientResponse, ClientListResponse
from app.auth import get_current_user
from app.redis_client import redis_client

router = APIRouter()


@router.get("", response_model=ClientListResponse)
async def list_clients(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of clients for current user"""
    query = select(Client).where(Client.user_id == current_user.id)
    
    if status_filter:
        query = query.where(Client.status == status_filter)
    
    result = await db.execute(query)
    clients = result.scalars().all()
    
    return ClientListResponse(total=len(clients), clients=clients)


@router.post("", response_model=ClientResponse)
async def create_client(
    client_data: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Register a new client"""
    client = Client(
        user_id=current_user.id,
        hostname=client_data.hostname,
        client_token=secrets.token_urlsafe(32),
        os=client_data.os,
        platform=client_data.platform,
        arch=client_data.arch,
        agent_version=client_data.agent_version
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    
    return client


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get client details"""
    result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.user_id == current_user.id
        )
    )
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Get real-time status from Redis
    redis_status = await redis_client.get_client_status(str(client_id))
    if redis_status:
        client.status = redis_status.get("status", client.status)
    
    return client


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a client"""
    result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.user_id == current_user.id
        )
    )
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    await db.delete(client)
    await db.commit()
    
    return {"message": "Client deleted successfully"}


@router.post("/{client_id}/regenerate-token", response_model=ClientResponse)
async def regenerate_client_token(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Regenerate client token"""
    result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.user_id == current_user.id
        )
    )
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    client.client_token = secrets.token_urlsafe(32)
    await db.commit()
    await db.refresh(client)
    
    return client
