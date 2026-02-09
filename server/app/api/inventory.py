"""
Inventory API Routes
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.client import Client
from app.models.inventory import InventoryLatest, InventoryHistory, PowerHistory
from app.schemas.inventory import InventoryResponse, BMCInfo
from app.auth import get_current_user

router = APIRouter()


def extract_bmc_info(raw_data: Optional[Dict[str, Any]]) -> Optional[BMCInfo]:
    """Extract BMC info from raw_data"""
    if not raw_data:
        return None
    
    # Check for hybrid mode data
    bmc_data = raw_data.get("bmc")
    if not bmc_data:
        return None
    
    return BMCInfo(
        bmc_type=bmc_data.get("bmc_type"),
        bmc_version=bmc_data.get("bmc_version"),
        bmc_ip=bmc_data.get("bmc_ip"),
        manufacturer=bmc_data.get("manufacturer"),
        model=bmc_data.get("model"),
        serial_number=bmc_data.get("serial_number"),
        sku=bmc_data.get("sku"),
        bios_version=bmc_data.get("bios_version"),
        uuid=bmc_data.get("uuid"),
        power_state=bmc_data.get("power_state"),
        power_consumed_watts=bmc_data.get("power_consumed_watts"),
        health_status=bmc_data.get("health_status"),
        processors=bmc_data.get("processors"),
        memory_total=bmc_data.get("memory_total"),
        memory_modules=bmc_data.get("memory_modules"),
        storage=bmc_data.get("storage"),
        power_supplies=bmc_data.get("power_supplies"),
        fans=bmc_data.get("fans"),
        temperatures=bmc_data.get("temperatures"),
    )


@router.get("/{client_id}")
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
    
    # Build response with BMC data
    response = {
        "client_id": inventory.client_id,
        "hostname": inventory.hostname,
        "os": inventory.os,
        "platform": inventory.platform,
        "arch": inventory.arch,
        "cpu_count": inventory.cpu_count,
        "cpu_model": inventory.cpu_model,
        "memory_total": inventory.memory_total,
        "memory_used": inventory.memory_used,
        "memory_free": inventory.memory_free,
        "disk_total": inventory.disk_total,
        "disk_used": inventory.disk_used,
        "disk_free": inventory.disk_free,
        "ip_addresses": inventory.ip_addresses,
        "mac_addresses": inventory.mac_addresses,
        "collected_at": inventory.collected_at,
        "raw_data": inventory.raw_data,
        "bmc": extract_bmc_info(inventory.raw_data)
    }
    
    return response


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


@router.get("/{client_id}/power/history")
async def get_power_history(
    client_id: str,
    hours: int = 24,
    limit: int = 500,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get power consumption history for charting"""
    from datetime import datetime, timedelta
    
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
    
    # Calculate time range
    since = datetime.utcnow() - timedelta(hours=hours)
    
    # Get power history
    result = await db.execute(
        select(PowerHistory)
        .where(
            PowerHistory.client_id == client_id,
            PowerHistory.recorded_at >= since
        )
        .order_by(PowerHistory.recorded_at.asc())
        .limit(limit)
    )
    history = result.scalars().all()
    
    return {
        "client_id": str(client_id),
        "since": since.isoformat(),
        "total": len(history),
        "data": [
            {
                "timestamp": h.recorded_at.isoformat() if h.recorded_at else None,
                "power_watts": h.power_consumed_watts,
                "avg_watts": h.avg_power_watts,
                "min_watts": h.min_power_watts,
                "max_watts": h.max_power_watts
            }
            for h in history
        ]
    }
