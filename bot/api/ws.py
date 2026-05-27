from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect

from bot.api.broadcast import broadcast_state, register, unregister
from bot.api.state import build_state_payload
from bot.config import get_settings


async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    register(ws)
    interval = get_settings().dashboard_ws_interval_ms / 1000.0
    try:
        payload = await build_state_payload()
        await ws.send_text(json.dumps(payload))
        while True:
            await asyncio.sleep(interval)
            payload = await build_state_payload()
            await ws.send_text(json.dumps(payload))
    except WebSocketDisconnect:
        pass
    finally:
        unregister(ws)
