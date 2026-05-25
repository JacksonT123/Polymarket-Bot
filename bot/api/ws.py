"""
WebSocket fanout: polls events_outbox table every 100ms,
broadcasts new events to all connected dashboard clients.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from bot.ledger.db import get_db
from bot.observability.log import get_logger

log = get_logger(__name__)
router = APIRouter()

_POLL_MS = 100  # poll outbox every 100ms
_clients: set[WebSocket] = set()


@router.websocket("/ws/events")
async def events_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    _clients.add(websocket)
    log.info("ws_client_connected", total=len(_clients))

    try:
        # Send initial ping
        await websocket.send_json({"type": "connected"})

        # Keep alive — fanout task handles sending
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if msg == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)
        log.info("ws_client_disconnected", total=len(_clients))


async def run_fanout() -> None:
    """
    Background task: polls events_outbox, broadcasts to all WS clients.
    Run this as a background asyncio task alongside the FastAPI server.
    """
    last_id = 0

    async with get_db() as db:
        # Start from latest to avoid replaying history on startup
        async with db.execute("SELECT MAX(id) FROM events_outbox") as cur:
            row = await cur.fetchone()
        if row and row[0]:
            last_id = row[0]

    log.info("fanout_start", last_id=last_id)

    while True:
        await asyncio.sleep(_POLL_MS / 1000)

        if not _clients:
            continue

        try:
            async with get_db() as db:
                async with db.execute(
                    "SELECT id, event_type, payload, created_at FROM events_outbox WHERE id > ? ORDER BY id LIMIT 50",
                    (last_id,),
                ) as cur:
                    rows = await cur.fetchall()

            if not rows:
                continue

            last_id = rows[-1][0]

            for row in rows:
                event_id, event_type, payload_str, created_at = row
                try:
                    payload = json.loads(payload_str) if payload_str else {}
                except json.JSONDecodeError:
                    payload = {"raw": payload_str}

                message = {
                    "type": event_type,
                    "id": event_id,
                    "ts": created_at,
                    "payload": payload,
                }

                dead = set()
                for client in list(_clients):
                    try:
                        await client.send_json(message)
                    except Exception:
                        dead.add(client)

                _clients.difference_update(dead)

        except Exception as e:
            log.error("fanout_error", error=str(e))
