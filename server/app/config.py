"""
Server Configuration
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8080
    SERVER_URL: str = "https://agent.example.com"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agentdb"
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 15
    WS_OFFLINE_TIMEOUT: int = 60
    
    # Security
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # Binary Storage
    BINARY_STORAGE_PATH: str = "/storage/binaries"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
