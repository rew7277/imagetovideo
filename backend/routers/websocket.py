"""
WebSocket Router — Real-time collaboration.
Broadcasts drawing strokes to all users in the same canvas room.
"""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, List

router = APIRouter()


class ConnectionManager:
    """
    Manages WebSocket connections grouped by canvas room.
    Each canvas_id is a "room" — all connected clients receive each other's strokes.
    """

    def __init__(self):
        # room_id (canvas_id) -> list of active WebSocket connections
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        """Accept connection and add to room."""
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = []
        self.rooms[room_id].append(websocket)
        print(f"[WS] Client joined room {room_id}. Total: {len(self.rooms[room_id])}")

    def disconnect(self, websocket: WebSocket, room_id: str):
        """Remove connection from room."""
        if room_id in self.rooms:
            self.rooms[room_id].remove(websocket)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
        print(f"[WS] Client left room {room_id}")

    async def broadcast(self, message: dict, room_id: str, sender: WebSocket):
        """
        Send a message to all clients in the room EXCEPT the sender.
        This avoids echo effects on the drawing canvas.
        """
        if room_id not in self.rooms:
            return
        dead_sockets = []
        for connection in self.rooms[room_id]:
            if connection is not sender:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    dead_sockets.append(connection)
        # Clean up any broken connections found during broadcast
        for ws in dead_sockets:
            self.rooms[room_id].remove(ws)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/draw/{canvas_id}")
async def websocket_draw(
    websocket: WebSocket,
    canvas_id: str,
    token: str = Query(default=None),  # JWT passed as query param for WS auth
):
    """
    WebSocket endpoint for real-time drawing collaboration.
    
    Message format (JSON):
    {
        "type": "stroke",        # stroke | clear | cursor
        "x": 100,
        "y": 200,
        "color": "#ff0000",
        "size": 5,
        "tool": "pen",           # pen | eraser
        "isNewStroke": true      # true = start of new stroke, false = continuation
    }
    """
    # Optional: validate JWT token here for production
    # For now we accept all connections and trust canvas_id scoping

    room_id = canvas_id
    await manager.connect(websocket, room_id)

    try:
        while True:
            # Wait for drawing event from this client
            raw_data = await websocket.receive_text()
            try:
                message = json.loads(raw_data)
            except json.JSONDecodeError:
                continue  # Ignore malformed messages

            # Broadcast to all other clients in the same room
            await manager.broadcast(message, room_id, sender=websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        # Notify others that a collaborator left
        await manager.broadcast(
            {"type": "user_left", "room": room_id},
            room_id,
            sender=websocket,
        )
