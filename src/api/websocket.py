"""WebSocket endpoint — pushes live bot events to the dashboard."""
import asyncio
import json
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import structlog

log = structlog.get_logger(__name__)

_connections: list[WebSocket] = []


async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _connections.append(websocket)
    log.info("ws_client_connected", total=len(_connections))
    try:
        while True:
            # Keep alive — client sends pings; we echo
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        _connections.remove(websocket)
        log.info("ws_client_disconnected", total=len(_connections))


async def broadcast(event_type: str, payload: dict) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    if not _connections:
        return
    message = json.dumps({
        "type": event_type,
        "ts": datetime.utcnow().isoformat(),
        "data": payload,
    })
    dead = []
    for ws in _connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connections.remove(ws)
