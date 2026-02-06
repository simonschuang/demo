"""
Redis Client for Presence Management
"""
import logging
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self):
        self.client: redis.Redis = None
        self.connected = False
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
            # Test connection
            await self.client.ping()
            self.connected = True
            logger.info("Redis connected")
        except Exception as e:
            self.connected = False
            logger.warning(f"Redis not available: {e}")
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client and self.connected:
            await self.client.close()
            self.connected = False
    
    async def set_client_online(self, client_id: str, pod_id: str = None):
        """Set client status to online"""
        if not self.connected:
            return
        try:
            import time
            key = f"client:{client_id}"
            await self.client.hset(key, mapping={
                "status": "online",
                "last_heartbeat": str(time.time()),
                "pod_id": pod_id or "default"
            })
            await self.client.expire(key, 120)
        except Exception as e:
            logger.warning(f"Redis error in set_client_online: {e}")
    
    async def set_client_offline(self, client_id: str):
        """Set client status to offline"""
        if not self.connected:
            return
        try:
            key = f"client:{client_id}"
            await self.client.hset(key, "status", "offline")
        except Exception as e:
            logger.warning(f"Redis error in set_client_offline: {e}")
    
    async def update_heartbeat(self, client_id: str):
        """Update client heartbeat timestamp"""
        if not self.connected:
            return
        try:
            import time
            key = f"client:{client_id}"
            await self.client.hset(key, "last_heartbeat", str(time.time()))
            await self.client.expire(key, 120)
        except Exception as e:
            logger.warning(f"Redis error in update_heartbeat: {e}")
    
    async def get_client_status(self, client_id: str) -> dict:
        """Get client status from Redis"""
        if not self.connected:
            return {}
        try:
            key = f"client:{client_id}"
            return await self.client.hgetall(key)
        except Exception as e:
            logger.warning(f"Redis error in get_client_status: {e}")
            return {}
    
    async def get_all_clients_status(self) -> dict:
        """Get all clients status"""
        if not self.connected:
            return {}
        try:
            clients = {}
            async for key in self.client.scan_iter("client:*"):
                client_id = key.split(":")[1]
                clients[client_id] = await self.client.hgetall(key)
            return clients
        except Exception as e:
            logger.warning(f"Redis error in get_all_clients_status: {e}")
            return {}


# Global Redis client instance
redis_client = RedisClient()
