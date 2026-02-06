"""
WebSocket Message Schemas
"""
from typing import Optional, Any, Dict
from pydantic import BaseModel


class WSMessage(BaseModel):
    type: str
    data: Optional[Dict[str, Any]] = None
    timestamp: int
    message_id: Optional[str] = None


class HeartbeatData(BaseModel):
    status: str = "alive"
    uptime: Optional[int] = None


class InventoryMessage(BaseModel):
    hostname: Optional[str] = None
    os: Optional[str] = None
    platform: Optional[str] = None
    arch: Optional[str] = None
    cpu_count: Optional[int] = None
    cpu_model: Optional[str] = None
    memory_total: Optional[int] = None
    memory_used: Optional[int] = None
    disk_total: Optional[int] = None
    disk_used: Optional[int] = None
    ip_addresses: Optional[list] = None
    mac_addresses: Optional[list] = None
    raw_data: Optional[Dict[str, Any]] = None
