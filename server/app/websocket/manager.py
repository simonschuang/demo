"""
WebSocket Connection Manager
"""
import os
import time
import json
import logging
from typing import Dict, Optional
from fastapi import WebSocket

from app.redis_client import redis_client

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        # Active connections: client_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        self.pod_id = os.environ.get("POD_ID", "default")
    
    async def connect(self, client_id: str, websocket: WebSocket):
        """Accept WebSocket connection and register client"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        
        # Update Redis presence
        await redis_client.set_client_online(client_id, self.pod_id)
        
        logger.info(f"Client {client_id} connected")
        
        # Send welcome message
        await self.send_welcome(client_id)
    
    async def disconnect(self, client_id: str):
        """Handle client disconnection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        # Update Redis status
        await redis_client.set_client_offline(client_id)
        
        logger.info(f"Client {client_id} disconnected")
    
    async def send_welcome(self, client_id: str):
        """Send welcome message to client"""
        from app.config import settings
        
        welcome_msg = {
            "type": "welcome",
            "data": {
                "client_id": client_id,
                "server_version": "v1.0.0",
                "heartbeat_interval": settings.WS_HEARTBEAT_INTERVAL,
                "inventory_interval": 60
            },
            "timestamp": int(time.time())
        }
        await self.send_message(client_id, welcome_msg)
    
    async def send_message(self, client_id: str, message: dict):
        """Send message to specific client"""
        websocket = self.active_connections.get(client_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")
                await self.disconnect(client_id)
    
    async def send_heartbeat_ack(self, client_id: str):
        """Send heartbeat acknowledgment"""
        ack_msg = {
            "type": "heartbeat_ack",
            "data": {
                "server_time": int(time.time())
            },
            "timestamp": int(time.time())
        }
        await self.send_message(client_id, ack_msg)
    
    async def send_inventory_ack(self, client_id: str, changed: bool = False):
        """Send inventory acknowledgment"""
        ack_msg = {
            "type": "inventory_ack",
            "data": {
                "received": True,
                "changed": changed
            },
            "timestamp": int(time.time())
        }
        await self.send_message(client_id, ack_msg)
    
    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        """Broadcast message to all connected clients"""
        for client_id, websocket in self.active_connections.items():
            if client_id != exclude:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast to {client_id}: {e}")
    
    def is_connected(self, client_id: str) -> bool:
        """Check if client is connected"""
        return client_id in self.active_connections
    
    def get_connected_clients(self) -> list:
        """Get list of connected client IDs"""
        return list(self.active_connections.keys())


# Global connection manager instance
connection_manager = ConnectionManager()
