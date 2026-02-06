"""
Client Schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ClientCreate(BaseModel):
    hostname: Optional[str] = None
    os: Optional[str] = None
    platform: Optional[str] = None
    arch: Optional[str] = None
    agent_version: Optional[str] = None


class ClientResponse(BaseModel):
    id: str
    user_id: str
    hostname: Optional[str] = None
    client_token: str
    status: str
    os: Optional[str] = None
    platform: Optional[str] = None
    arch: Optional[str] = None
    agent_version: Optional[str] = None
    registered_at: datetime
    first_connected_at: Optional[datetime] = None
    last_connected_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    ip_address: Optional[str] = None
    
    class Config:
        from_attributes = True


class ClientListResponse(BaseModel):
    total: int
    clients: List[ClientResponse]
