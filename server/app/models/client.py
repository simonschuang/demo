"""
Client Model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


def generate_uuid():
    return str(uuid.uuid4())


class Client(Base):
    __tablename__ = "clients"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    hostname = Column(String(255), nullable=True)
    client_token = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(50), default="offline", index=True)
    
    # Basic info
    os = Column(String(50), nullable=True)
    platform = Column(String(100), nullable=True)
    arch = Column(String(50), nullable=True)
    agent_version = Column(String(50), nullable=True)
    
    # Time records
    registered_at = Column(DateTime, default=datetime.utcnow)
    first_connected_at = Column(DateTime, nullable=True)
    last_connected_at = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True, index=True)
    
    # Connection info
    ip_address = Column(String(45), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="clients")
    inventory_latest = relationship("InventoryLatest", back_populates="client", uselist=False, cascade="all, delete-orphan")
    inventory_history = relationship("InventoryHistory", back_populates="client", cascade="all, delete-orphan")
    power_history = relationship("PowerHistory", back_populates="client", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Client(id={self.id}, hostname={self.hostname}, status={self.status})>"
