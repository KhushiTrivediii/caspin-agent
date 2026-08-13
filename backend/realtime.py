import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger("realtime")


class ConnectionManager:
    """
    Manages active native WebSocket connections to broadcast real-time operational events.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Active connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast JSON message to all active WebSocket clients."""
        disconnected_sockets = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to socket, marking for removal: {e}")
                disconnected_sockets.append(connection)

        # Cleanup dead sockets
        for dead_socket in disconnected_sockets:
            self.disconnect(dead_socket)

    async def emit_ticket_update(self, ticket_id: str, status: str, payload: dict):
        """Broadcast when a ticket is created or modified."""
        await self.broadcast({
            "type": "ticket_update",
            "ticket_id": ticket_id,
            "status": status,
            "data": payload
        })

    async def emit_sla_breach_alert(self, ticket_id: str, product: str, stage: str, stalled_since: str):
        """Broadcast SLA breach alert warnings."""
        await self.broadcast({
            "type": "sla_breach_alert",
            "ticket_id": ticket_id,
            "product": product,
            "stage": stage,
            "stalled_since": stalled_since
        })


# Global singleton instance
realtime_manager = ConnectionManager()
