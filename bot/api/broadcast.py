"""Push live dashboard updates to connected WebSocket clients."""
from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket

from bot.api.state import build_state_payload

_clients: set[WebSocket] = set()
_lock = asyncio.Lock()
_version = 0


def register(ws: WebSocket) -> None:
    _clients.add(ws)


def unregister(ws: WebSocket) -> None:
    _clients.discard(ws)


async def broadcast_state(*, force_mtm: bool = False) -> None:
    global _version
    if not _clients:
        return
    if force_mtm:
        from bot.portfolio.mtm import invalidate_cache

        invalidate_cache()
    payload = await build_state_payload(force_mtm=force_mtm)
    _version += 1
    payload["push_version"] = _version
    text = json.dumps(payload)
    dead: list[WebSocket] = []
    for ws in list(_clients):
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        unregister(ws)


def schedule_broadcast(*, force_mtm: bool = False) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_state(force_mtm=force_mtm))
    except RuntimeError:
        pass
