"""
Inventory API Routes
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.client import Client
from app.models.inventory import InventoryLatest, InventoryHistory
from app.schemas.inventory import InventoryResponse
from app.auth import get_current_user

router = APIRouter()


@router.get("/{client_id}", response_model=InventoryResponse)
async def get_client_inventory(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get latest inventory for a client"""
    # Verify client belongs to user
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
    
    # Get latest inventory
    result = await db.execute(
        select(InventoryLatest).where(InventoryLatest.client_id == client_id)
    )
    inventory = result.scalar_one_or_none()
    
    if not inventory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory not found"
        )
    
    return inventory


@router.get("/{client_id}/history")
async def get_inventory_history(
    client_id: str,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get inventory history for a client"""
    # Verify client belongs to user
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
    
    # Get history
    result = await db.execute(
        select(InventoryHistory)
        .where(InventoryHistory.client_id == client_id)
        .order_by(InventoryHistory.collected_at.desc())
        .limit(limit)
    )
    history = result.scalars().all()
    
    return {
        "client_id": str(client_id),
        "total": len(history),
        "history": [
            {
                "id": h.id,
                "inventory_data": h.inventory_data,
                "collected_at": h.collected_at.isoformat() if h.collected_at else None
            }
            for h in history
        ]
    }
