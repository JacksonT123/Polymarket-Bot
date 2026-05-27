import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from bot.api.state import build_state_payload
from bot.api.ws import websocket_endpoint
from bot.config import get_settings
from bot.data import rate_limit
from bot.engine.redeem import redeem_resolved_positions
from bot.engine.runner import CopyEngine
from bot.ingest.chain_listener import chain_listener_loop
from bot.leader_ranker.pipeline import run_discovery
from bot.leader_ranker.scheduler import discovery_scheduler
from bot.ledger import repo
from bot.ledger.db import init_db
from bot.observability.log import configure_logging, get_logger

log = get_logger(__name__)
_stop = asyncio.Event()
_engine: CopyEngine | None = None
_tasks: list[asyncio.Task] = []


async def _redeem_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            n = await redeem_resolved_positions()
            if n:
                log.info("redeem_pass_complete", count=n)
        except Exception as e:
            log.error("redeem_error", error=str(e))
        try:
            await asyncio.wait_for(stop.wait(), timeout=300.0)
        except asyncio.TimeoutError:
            pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _engine, _tasks
    configure_logging()
    await init_db()
    cfg = get_settings()
    rate_limit.reset_stats()

    leaders = await repo.get_leaders(status="active")
    if leaders:
        log.info("startup_roster_cached", count=len(leaders))
    elif cfg.auto_discover_leaders:
        log.info("startup_discovery_blocking")
        try:
            await run_discovery()
            leaders = await repo.get_leaders(status="active")
            log.info("startup_discovery_done", active=len(leaders))
        except Exception as e:
            log.error("startup_discovery_failed", error=str(e))

    _engine = CopyEngine()
    roster = {r["proxy"] for r in leaders}

    _tasks = [
        asyncio.create_task(_engine.run_loop(_stop), name="copy_engine"),
        asyncio.create_task(discovery_scheduler(_stop), name="discovery_scheduler"),
        asyncio.create_task(_redeem_loop(_stop), name="redeem_loop"),
        asyncio.create_task(chain_listener_loop(_stop, roster), name="chain_listener"),
    ]
    log.info("bot_running", dashboard=f"http://{cfg.api_host}:{cfg.api_port}/dashboard", mode=cfg.bot_mode)
    yield
    _stop.set()
    for t in _tasks:
        t.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)
    if _engine:
        await _engine.close()


app = FastAPI(title="Polymarket Copy Trader", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    cfg = get_settings()
    return {"ok": True, "mode": cfg.bot_mode, "live_ready": cfg.live_ready}


@app.get("/api/state")
async def state() -> dict:
    return await build_state_payload()


@app.post("/api/discovery/run")
async def trigger_discovery() -> dict:
    leaders = await run_discovery()
    return {"ok": True, "active": len(leaders)}


@app.websocket("/ws")
async def ws_route(ws: WebSocket) -> None:
    await websocket_endpoint(ws)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> str:
    path = Path(__file__).with_name("dashboard.html")
    return path.read_text(encoding="utf-8")
