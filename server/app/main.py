"""
Agent Monitor Server - Main Application
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import init_db, async_session_maker
from app.redis_client import redis_client
from app.api import api_router
from app.websocket.manager import connection_manager
from app.websocket.handler import handle_websocket_message
from app.auth import verify_client_token

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Agent Monitor Server...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Connect to Redis
    try:
        await redis_client.connect()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await redis_client.disconnect()


# Create FastAPI app
app = FastAPI(
    title="Agent Monitor Server",
    description="Client-Server架構的Agent監控與管理平台",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Agent Monitor Server",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    token: str = Query(...)
):
    """WebSocket endpoint for agent connections"""
    # Verify token
    async with async_session_maker() as db:
        client_info = await verify_client_token(token, db)
        
        if not client_info or client_info["client_id"] != client_id:
            await websocket.close(code=1008, reason="Authentication failed")
            return
        
        # Accept connection
        await connection_manager.connect(client_id, websocket)
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                
                # Handle message with new session
                async with async_session_maker() as msg_db:
                    await handle_websocket_message(client_id, data, msg_db)
                    
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"WebSocket error for {client_id}: {e}")
        finally:
            await connection_manager.disconnect(client_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG
    )
