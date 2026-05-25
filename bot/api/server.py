"""
FastAPI control plane — binds to 127.0.0.1:8787 only (never exposed to network).
Mounts all route modules and the WebSocket fanout.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bot.api import ws
from bot.api.routes import kill_switch, leaders, positions, settings, state
from bot.ledger.db import close_db, init_db
from bot.observability.log import get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("api_server_start")
    yield
    await close_db()
    log.info("api_server_stop")


app = FastAPI(
    title="Polymarket Copy-Trading Bot",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# Allow Next.js dev server on :3000 and production same-origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(state.router, prefix="/api/state", tags=["state"])
app.include_router(positions.router, prefix="/api/positions", tags=["positions"])
app.include_router(leaders.router, prefix="/api/leaders", tags=["leaders"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(kill_switch.router, prefix="/api/kill-switch", tags=["kill-switch"])

# WebSocket
app.include_router(ws.router, tags=["websocket"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
