"""
SQLite connection manager (aiosqlite) with WAL mode and schema bootstrap.
Single shared connection — SQLite WAL handles concurrent readers fine.
"""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

from bot.config import get_settings
from bot.observability.log import get_logger

log = get_logger(__name__)

_SCHEMA_SQL = Path(__file__).parent / "schemas.sql"
_conn: aiosqlite.Connection | None = None


async def init_db() -> None:
    """Open the database, apply WAL pragmas, and run the schema DDL."""
    global _conn
    if _conn is not None:
        return  # already initialized (e.g. called from both main.py and server lifespan)
    cfg = get_settings()
    db_path = cfg.database_path

    _conn = await aiosqlite.connect(str(db_path))
    _conn.row_factory = aiosqlite.Row

    await _conn.execute("PRAGMA journal_mode=WAL")
    await _conn.execute("PRAGMA synchronous=NORMAL")
    await _conn.execute("PRAGMA cache_size=-65536")
    await _conn.execute("PRAGMA mmap_size=268435456")
    await _conn.execute("PRAGMA foreign_keys=ON")
    await _conn.commit()

    schema = _SCHEMA_SQL.read_text(encoding="utf-8")
    await _conn.executescript(schema)
    await _conn.commit()

    log.info("db_initialized", path=str(db_path))


async def close_db() -> None:
    global _conn
    if _conn:
        await _conn.close()
        _conn = None


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    if _conn is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    yield _conn


async def write_event(event_name: str, payload: dict | None = None) -> None:
    """
    Write a structured event to events table and enqueue in events_outbox
    for WebSocket fanout to dashboard clients.
    """
    payload_json = json.dumps(payload) if payload else None
    ts = int(time.time())

    async with get_db() as db:
        await db.execute(
            "INSERT INTO events (event_name, payload_json, ts) VALUES (?,?,?)",
            (event_name, payload_json, ts),
        )
        await db.execute(
            "INSERT INTO events_outbox (event_type, payload, created_at) VALUES (?,?,?)",
            (event_name, payload_json, ts),
        )
        await db.commit()


async def vacuum_db() -> None:
    """WAL checkpoint + VACUUM. Called nightly after ranking job."""
    async with get_db() as db:
        await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        await db.execute("VACUUM")
        await db.commit()
    log.info("db_vacuumed")
