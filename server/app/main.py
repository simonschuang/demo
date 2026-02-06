"""
Agent Monitor Server - Main Application
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import init_db, async_session_maker
from app.redis_client import redis_client
from app.api import api_router
from app.websocket.manager import connection_manager
from app.websocket.handler import handle_websocket_message
from app.auth import verify_client_token, get_current_user
from app.terminal.proxy import terminal_proxy

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"


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
    
    # Configure terminal proxy to send messages to clients
    async def send_to_client(client_id: str, message_type: str, data: dict):
        import time
        message = {
            "type": message_type,
            "data": data,
            "timestamp": int(time.time())
        }
        await connection_manager.send_message(client_id, message)
    
    terminal_proxy.set_client_sender(send_to_client)
    logger.info("Terminal proxy initialized")
    
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

# Mount static files
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/")
async def root():
    """Serve the main web application"""
    index_path = WEB_DIR / "templates" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
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
            # Close any terminal sessions for this client
            terminal_proxy.close_client_sessions(client_id)
            
            # Update client status to offline in database
            async with async_session_maker() as disconnect_db:
                from sqlalchemy import select
                from app.models.client import Client
                result = await disconnect_db.execute(select(Client).where(Client.id == client_id))
                client = result.scalar_one_or_none()
                if client:
                    client.status = "offline"
                    await disconnect_db.commit()
            await connection_manager.disconnect(client_id)


@app.websocket("/ws/terminal/{client_id}")
async def terminal_websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    token: str = Query(...)
):
    """
    WebSocket endpoint for browser terminal connections.
    
    This endpoint connects a browser user to a terminal session on a remote client.
    """
    # Verify user token (this is a user accessing terminal, not a client connecting)
    async with async_session_maker() as db:
        try:
            from app.auth import verify_token
            payload = verify_token(token)
            if not payload:
                await websocket.close(code=1008, reason="Invalid token")
                return
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            await websocket.close(code=1008, reason="Authentication failed")
            return
        
        # Check if target client is online
        if not connection_manager.is_connected(client_id):
            await websocket.close(code=1008, reason="Client not connected")
            return
        
        # Accept the WebSocket connection
        await websocket.accept()
        
        session_id = None
        
        try:
            # Wait for initial message with terminal config
            init_data = await websocket.receive_json()
            
            cols = init_data.get("cols", 80)
            rows = init_data.get("rows", 24)
            shell = init_data.get("shell", "")
            
            # Create terminal session
            session_id = await terminal_proxy.create_session(
                client_id=client_id,
                user_websocket=websocket,
                cols=cols,
                rows=rows,
                shell=shell
            )
            
            if not session_id:
                await websocket.send_json({
                    "type": "terminal_error",
                    "error": "Failed to create terminal session"
                })
                await websocket.close(code=1011, reason="Failed to create session")
                return
                
            # Send session confirmation
            await websocket.send_json({
                "type": "terminal_ready",
                "session_id": session_id
            })
            
            # Main message loop
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "")
                
                if msg_type == "input":
                    # Forward input to client
                    await terminal_proxy.send_input(session_id, data.get("data", ""))
                    
                elif msg_type == "resize":
                    # Resize terminal
                    await terminal_proxy.resize_terminal(
                        session_id,
                        data.get("cols", 80),
                        data.get("rows", 24)
                    )
                    
                elif msg_type == "close":
                    # User requested close
                    break
                    
        except WebSocketDisconnect:
            logger.info(f"Terminal WebSocket disconnected for client {client_id}")
        except Exception as e:
            logger.error(f"Terminal WebSocket error: {e}")
        finally:
            if session_id:
                await terminal_proxy.close_session(session_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG
    )
