"""
Inventory Models
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, Numeric, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship

from app.models.base import Base


class InventoryLatest(Base):
    __tablename__ = "inventory_latest"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(36), ForeignKey("clients.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Common fields
    hostname = Column(String(255), nullable=True)
    os = Column(String(50), nullable=True)
    platform = Column(String(100), nullable=True)
    arch = Column(String(50), nullable=True)
    
    # CPU info
    cpu_count = Column(Integer, nullable=True)
    cpu_model = Column(String(255), nullable=True)
    cpu_usage_percent = Column(Numeric(5, 2), nullable=True)
    
    # Memory info
    memory_total = Column(BigInteger, nullable=True)
    memory_used = Column(BigInteger, nullable=True)
    memory_free = Column(BigInteger, nullable=True)
    memory_usage_percent = Column(Numeric(5, 2), nullable=True)
    
    # Disk info
    disk_total = Column(BigInteger, nullable=True)
    disk_used = Column(BigInteger, nullable=True)
    disk_free = Column(BigInteger, nullable=True)
    disk_usage_percent = Column(Numeric(5, 2), nullable=True)
    
    # Network info (stored as JSON string for SQLite compatibility)
    ip_addresses = Column(JSON, nullable=True)
    mac_addresses = Column(JSON, nullable=True)
    
    # Timestamps
    collected_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Raw data (JSON)
    raw_data = Column(JSON, nullable=True)
    
    # Relationship
    client = relationship("Client", back_populates="inventory_latest")
    
    def __repr__(self):
        return f"<InventoryLatest(client_id={self.client_id}, hostname={self.hostname})>"


class InventoryHistory(Base):
    __tablename__ = "inventory_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(36), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Snapshot of inventory data
    inventory_data = Column(JSON, nullable=False)
    
    # Timestamps
    collected_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    client = relationship("Client", back_populates="inventory_history")
    
    def __repr__(self):
        return f"<InventoryHistory(client_id={self.client_id}, collected_at={self.collected_at})>"


class PowerHistory(Base):
    """Stores power consumption history for charting"""
    __tablename__ = "power_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(36), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Power data
    power_consumed_watts = Column(Integer, nullable=False)
    
    # Optional additional metrics
    avg_power_watts = Column(Integer, nullable=True)
    min_power_watts = Column(Integer, nullable=True)
    max_power_watts = Column(Integer, nullable=True)
    
    # Timestamp
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationship
    client = relationship("Client", back_populates="power_history")
    
    def __repr__(self):
        return f"<PowerHistory(client_id={self.client_id}, power={self.power_consumed_watts}W, at={self.recorded_at})>"
