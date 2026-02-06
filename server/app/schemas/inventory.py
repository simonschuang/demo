"""
Inventory Schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class InventoryData(BaseModel):
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
    ip_addresses: Optional[List[str]] = None
    mac_addresses: Optional[List[str]] = None
    raw_data: Optional[Dict[str, Any]] = None


class InventoryResponse(BaseModel):
    client_id: str
    hostname: Optional[str] = None
    os: Optional[str] = None
    platform: Optional[str] = None
    arch: Optional[str] = None
    cpu_count: Optional[int] = None
    cpu_model: Optional[str] = None
    memory_total: Optional[int] = None
    memory_used: Optional[int] = None
    memory_free: Optional[int] = None
    disk_total: Optional[int] = None
    disk_used: Optional[int] = None
    disk_free: Optional[int] = None
    ip_addresses: Optional[List[str]] = None
    mac_addresses: Optional[List[str]] = None
    collected_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
