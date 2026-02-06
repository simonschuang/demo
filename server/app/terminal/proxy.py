# Terminal Proxy - WebSocket-based terminal proxy for remote terminal access
import asyncio
import base64
import logging
import uuid
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


@dataclass
class TerminalSession:
    """Represents an active terminal session"""
    session_id: str
    client_id: str
    user_websocket: WebSocket
    created_at: datetime = field(default_factory=datetime.utcnow)
    cols: int = 80
    rows: int = 24
    
    
class TerminalProxy:
    """
    Manages terminal sessions between browser users and connected clients.
    
    Flow:
    1. User opens terminal UI for a client
    2. Server creates a TerminalSession and sends 'terminal_command' (init) to client
    3. Client creates PTY and sends output back via 'terminal_output'
    4. Server forwards output to user's WebSocket
    5. User sends input, server forwards to client via 'terminal_command' (input)
    """
    
    def __init__(self):
        # session_id -> TerminalSession
        self._sessions: Dict[str, TerminalSession] = {}
        # client_id -> list of session_ids (a client can have multiple terminal sessions)
        self._client_sessions: Dict[str, list] = {}
        # Callback to send messages to clients
        self._send_to_client: Optional[Callable] = None
        
    def set_client_sender(self, sender: Callable):
        """
        Set the callback function to send messages to connected clients.
        
        Args:
            sender: async function(client_id: str, message_type: str, data: dict)
        """
        self._send_to_client = sender
        
    async def create_session(
        self,
        client_id: str,
        user_websocket: WebSocket,
        cols: int = 80,
        rows: int = 24,
        shell: str = ""
    ) -> Optional[str]:
        """
        Create a new terminal session for a client.
        
        Args:
            client_id: The ID of the target client
            user_websocket: The WebSocket connection from the browser
            cols: Terminal columns (default: 80)
            rows: Terminal rows (default: 24)
            shell: Preferred shell (empty for default)
            
        Returns:
            session_id if successful, None otherwise
        """
        if not self._send_to_client:
            logger.error("Client sender not configured")
            return None
            
        session_id = str(uuid.uuid4())
        
        session = TerminalSession(
            session_id=session_id,
            client_id=client_id,
            user_websocket=user_websocket,
            cols=cols,
            rows=rows
        )
        
        self._sessions[session_id] = session
        
        if client_id not in self._client_sessions:
            self._client_sessions[client_id] = []
        self._client_sessions[client_id].append(session_id)
        
        # Send init command to client
        try:
            await self._send_to_client(
                client_id,
                "terminal_command",
                {
                    "session_id": session_id,
                    "command": "init",
                    "cols": cols,
                    "rows": rows,
                    "shell": shell
                }
            )
            logger.info(f"Terminal session created: {session_id} for client {client_id}")
            return session_id
        except Exception as e:
            logger.error(f"Failed to send init command to client {client_id}: {e}")
            self._cleanup_session(session_id)
            return None
            
    async def send_input(self, session_id: str, data: str) -> bool:
        """
        Send terminal input to the client.
        
        Args:
            session_id: The terminal session ID
            data: The input data (keystrokes)
            
        Returns:
            True if successful
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return False
            
        if not self._send_to_client:
            return False
            
        try:
            await self._send_to_client(
                session.client_id,
                "terminal_command",
                {
                    "session_id": session_id,
                    "command": "input",
                    "data": data
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send input to session {session_id}: {e}")
            return False
            
    async def resize_terminal(self, session_id: str, cols: int, rows: int) -> bool:
        """
        Resize the terminal.
        
        Args:
            session_id: The terminal session ID
            cols: New column count
            rows: New row count
            
        Returns:
            True if successful
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return False
            
        if not self._send_to_client:
            return False
            
        session.cols = cols
        session.rows = rows
        
        try:
            await self._send_to_client(
                session.client_id,
                "terminal_command",
                {
                    "session_id": session_id,
                    "command": "resize",
                    "cols": cols,
                    "rows": rows
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to resize session {session_id}: {e}")
            return False
            
    async def close_session(self, session_id: str) -> bool:
        """
        Close a terminal session.
        
        Args:
            session_id: The terminal session ID
            
        Returns:
            True if successful
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
            
        if self._send_to_client:
            try:
                await self._send_to_client(
                    session.client_id,
                    "terminal_command",
                    {
                        "session_id": session_id,
                        "command": "close"
                    }
                )
            except Exception as e:
                logger.error(f"Failed to send close command to session {session_id}: {e}")
                
        self._cleanup_session(session_id)
        logger.info(f"Terminal session closed: {session_id}")
        return True
        
    def _cleanup_session(self, session_id: str):
        """Remove session from tracking dictionaries"""
        session = self._sessions.pop(session_id, None)
        if session:
            if session.client_id in self._client_sessions:
                try:
                    self._client_sessions[session.client_id].remove(session_id)
                    if not self._client_sessions[session.client_id]:
                        del self._client_sessions[session.client_id]
                except ValueError:
                    pass
                    
    async def handle_terminal_output(self, client_id: str, data: Dict[str, Any]):
        """
        Handle terminal output from a client.
        
        Args:
            client_id: The client ID that sent the output
            data: The output data containing session_id and output (base64 encoded)
        """
        session_id = data.get("session_id")
        output_b64 = data.get("output", "")
        output_type = data.get("type", "output")
        
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"Received output for unknown session: {session_id}")
            return
        
        # Decode base64 output
        try:
            output = base64.b64decode(output_b64).decode('utf-8', errors='replace')
        except Exception as e:
            logger.error(f"Failed to decode terminal output: {e}")
            output = output_b64  # Fall back to raw data
            
        try:
            # Forward output to user's browser
            await session.user_websocket.send_json({
                "type": "terminal_output",
                "session_id": session_id,
                "output": output,
                "output_type": output_type
            })
        except Exception as e:
            logger.error(f"Failed to forward output to user: {e}")
            # Session may be dead, clean up
            await self.close_session(session_id)
            
    async def handle_terminal_error(self, client_id: str, data: Dict[str, Any]):
        """
        Handle terminal error from a client.
        
        Args:
            client_id: The client ID that sent the error
            data: The error data containing session_id and error message
        """
        session_id = data.get("session_id")
        error = data.get("error", "Unknown error")
        
        session = self._sessions.get(session_id)
        if not session:
            return
            
        try:
            # Forward error to user's browser
            await session.user_websocket.send_json({
                "type": "terminal_error",
                "session_id": session_id,
                "error": error
            })
        except Exception as e:
            logger.error(f"Failed to forward error to user: {e}")
            
        # Clean up session on error
        self._cleanup_session(session_id)
        
    async def handle_terminal_closed(self, client_id: str, data: Dict[str, Any]):
        """
        Handle terminal closed notification from client.
        
        Args:
            client_id: The client ID
            data: Data containing session_id
        """
        session_id = data.get("session_id")
        
        session = self._sessions.get(session_id)
        if not session:
            return
            
        try:
            # Notify user that terminal was closed
            await session.user_websocket.send_json({
                "type": "terminal_closed",
                "session_id": session_id
            })
        except Exception:
            pass
            
        self._cleanup_session(session_id)
        logger.info(f"Terminal session closed by client: {session_id}")
        
    def close_client_sessions(self, client_id: str):
        """
        Close all terminal sessions for a client (when client disconnects).
        
        Args:
            client_id: The disconnected client's ID
        """
        session_ids = self._client_sessions.get(client_id, []).copy()
        for session_id in session_ids:
            session = self._sessions.get(session_id)
            if session:
                try:
                    # Notify user synchronously (best effort)
                    asyncio.create_task(
                        session.user_websocket.send_json({
                            "type": "terminal_closed",
                            "session_id": session_id,
                            "reason": "Client disconnected"
                        })
                    )
                except Exception:
                    pass
            self._cleanup_session(session_id)
            
        logger.info(f"Closed {len(session_ids)} terminal sessions for client {client_id}")
        
    def get_session(self, session_id: str) -> Optional[TerminalSession]:
        """Get a terminal session by ID"""
        return self._sessions.get(session_id)
        
    def get_client_sessions(self, client_id: str) -> list:
        """Get all terminal session IDs for a client"""
        return self._client_sessions.get(client_id, []).copy()
        
    @property
    def session_count(self) -> int:
        """Get total number of active sessions"""
        return len(self._sessions)


# Global terminal proxy instance
terminal_proxy = TerminalProxy()
