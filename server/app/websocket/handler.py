"""
WebSocket Message Handler
"""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.client import Client
from app.models.inventory import InventoryLatest, InventoryHistory
from app.redis_client import redis_client
from app.websocket.manager import connection_manager
from app.terminal.proxy import terminal_proxy

logger = logging.getLogger(__name__)


async def handle_websocket_message(client_id: str, message: dict, db: AsyncSession):
    """Handle incoming WebSocket message"""
    msg_type = message.get("type")
    data = message.get("data", {})
    
    logger.debug(f"Received message from {client_id}: type={msg_type}")
    
    if msg_type == "heartbeat":
        await handle_heartbeat(client_id, data, db)
    elif msg_type == "inventory":
        await handle_inventory(client_id, data, db)
    elif msg_type == "pong":
        # Response to ping, just log
        logger.debug(f"Received pong from {client_id}")
    elif msg_type == "terminal_output":
        # Terminal output from client
        await terminal_proxy.handle_terminal_output(client_id, data)
    elif msg_type == "terminal_error":
        # Terminal error from client
        await terminal_proxy.handle_terminal_error(client_id, data)
    elif msg_type == "terminal_closed":
        # Terminal closed by client
        await terminal_proxy.handle_terminal_closed(client_id, data)
    else:
        logger.warning(f"Unknown message type: {msg_type}")


async def handle_heartbeat(client_id: str, data: dict, db: AsyncSession):
    """Handle heartbeat message"""
    # Update Redis heartbeat
    await redis_client.update_heartbeat(client_id)
    
    # Update database last_seen
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client:
        client.last_seen = datetime.utcnow()
        client.status = "online"
        await db.commit()
    
    # Send heartbeat ack
    await connection_manager.send_heartbeat_ack(client_id)


async def handle_inventory(client_id: str, data: dict, db: AsyncSession):
    """Handle inventory message"""
    # Get client
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    
    if not client:
        logger.error(f"Client not found: {client_id}")
        return
    
    # Check if inventory exists
    result = await db.execute(
        select(InventoryLatest).where(InventoryLatest.client_id == client_id)
    )
    inventory = result.scalar_one_or_none()
    
    changed = False
    
    if inventory:
        # Check if data changed
        changed = has_inventory_changed(inventory, data)
        
        if changed:
            # Save to history
            history = InventoryHistory(
                client_id=client_id,
                inventory_data=inventory_to_dict(inventory),
                collected_at=inventory.collected_at or datetime.utcnow()
            )
            db.add(history)
        
        # Update latest
        update_inventory_from_data(inventory, data)
    else:
        # Create new inventory
        inventory = InventoryLatest(client_id=client_id)
        update_inventory_from_data(inventory, data)
        db.add(inventory)
        changed = True
    
    # Update client info
    client.hostname = data.get("hostname", client.hostname)
    client.os = data.get("os", client.os)
    client.platform = data.get("platform", client.platform)
    client.arch = data.get("arch", client.arch)
    
    await db.commit()
    
    # Send inventory ack
    await connection_manager.send_inventory_ack(client_id, changed)
    
    logger.info(f"Inventory updated for {client_id}, changed={changed}")


def has_inventory_changed(inventory: InventoryLatest, data: dict) -> bool:
    """Check if inventory has changed"""
    key_fields = [
        ("hostname", "hostname"),
        ("os", "os"),
        ("cpu_count", "cpu_count"),
        ("memory_total", "memory_total"),
        ("disk_total", "disk_total"),
    ]
    
    for inv_field, data_field in key_fields:
        old_value = getattr(inventory, inv_field, None)
        new_value = data.get(data_field)
        if old_value != new_value and new_value is not None:
            return True
    
    return False


def update_inventory_from_data(inventory: InventoryLatest, data: dict):
    """Update inventory object from data dict"""
    inventory.hostname = data.get("hostname")
    inventory.os = data.get("os")
    inventory.platform = data.get("platform")
    inventory.arch = data.get("arch")
    inventory.cpu_count = data.get("cpu_count")
    inventory.cpu_model = data.get("cpu_model")
    inventory.memory_total = data.get("memory_total")
    inventory.memory_used = data.get("memory_used")
    inventory.memory_free = data.get("memory_free")
    inventory.disk_total = data.get("disk_total")
    inventory.disk_used = data.get("disk_used")
    inventory.disk_free = data.get("disk_free")
    inventory.ip_addresses = data.get("ip_addresses")
    inventory.mac_addresses = data.get("mac_addresses")
    inventory.raw_data = data.get("raw_data")
    inventory.collected_at = datetime.utcnow()


def inventory_to_dict(inventory: InventoryLatest) -> dict:
    """Convert inventory object to dict for history"""
    return {
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
        "raw_data": inventory.raw_data,
        "collected_at": inventory.collected_at.isoformat() if inventory.collected_at else None
    }
