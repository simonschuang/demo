"""
Inventory Schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class ProcessorInfo(BaseModel):
    id: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    cores: Optional[int] = None
    threads: Optional[int] = None
    max_speed_mhz: Optional[int] = None
    status: Optional[str] = None


class MemoryModuleInfo(BaseModel):
    id: Optional[str] = None
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    serial_number: Optional[str] = None
    capacity_mib: Optional[int] = None
    speed_mhz: Optional[int] = None
    memory_type: Optional[str] = None
    status: Optional[str] = None


class FanInfo(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    speed_rpm: Optional[int] = None
    speed_percent: Optional[int] = None
    status: Optional[str] = None


class TemperatureInfo(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    reading_celsius: Optional[float] = None
    upper_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    status: Optional[str] = None


class PowerSupplyInfo(BaseModel):
    id: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    power_capacity_watts: Optional[int] = None
    power_output_watts: Optional[int] = None
    status: Optional[str] = None


class StorageInfo(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    capacity_gb: Optional[int] = None
    media_type: Optional[str] = None
    protocol: Optional[str] = None
    status: Optional[str] = None


class BMCInfo(BaseModel):
    bmc_type: Optional[str] = None
    bmc_version: Optional[str] = None
    bmc_ip: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    sku: Optional[str] = None
    bios_version: Optional[str] = None
    uuid: Optional[str] = None
    power_state: Optional[str] = None
    power_consumed_watts: Optional[int] = None
    health_status: Optional[str] = None
    processors: Optional[List[ProcessorInfo]] = None
    memory_total: Optional[int] = None
    memory_modules: Optional[List[MemoryModuleInfo]] = None
    storage: Optional[List[StorageInfo]] = None
    power_supplies: Optional[List[PowerSupplyInfo]] = None
    fans: Optional[List[FanInfo]] = None
    temperatures: Optional[List[TemperatureInfo]] = None


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
    raw_data: Optional[Dict[str, Any]] = None
    bmc: Optional[BMCInfo] = None
    
    class Config:
        from_attributes = True
