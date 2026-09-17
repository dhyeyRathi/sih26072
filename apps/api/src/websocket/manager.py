"""
WebSocket connection manager for real-time dashboard updates.
Broadcasts storm cell updates, forecasts, alerts, and data health changes.
"""

import json
import asyncio
from typing import Any
from fastapi import WebSocket
from datetime import datetime


class ConnectionManager:
    """Manages WebSocket connections and broadcasts updates to connected clients."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message_type: str, data: Any):
        """Broadcast a message to all connected clients."""
        payload = json.dumps({
            "type": message_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }, default=str)

        disconnected = []
        async with self._lock:
            for connection in self.active_connections:
                try:
                    await connection.send_text(payload)
                except Exception:
                    disconnected.append(connection)

            for conn in disconnected:
                self.active_connections.remove(conn)

    async def send_personal(self, websocket: WebSocket, message_type: str, data: Any):
        """Send a message to a specific client."""
        payload = json.dumps({
            "type": message_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }, default=str)
        await websocket.send_text(payload)


# Singleton
ws_manager = ConnectionManager()
