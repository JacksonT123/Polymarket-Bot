"""FastAPI application — dashboard backend + WebSocket event stream."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import structlog
import os

from src.api.routes import health, equity, wallets, positions, signals, funnel, config_routes, market_data
from src.api.websocket import ws_endpoint

log = structlog.get_logger(__name__)

app = FastAPI(
    title="Polymarket Copy Bot",
    version="2.3.0",
    docs_url="/api/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(health.router)
app.include_router(equity.router, prefix="/api")
app.include_router(wallets.router, prefix="/api")
app.include_router(positions.router, prefix="/api")
app.include_router(signals.router, prefix="/api")
app.include_router(funnel.router, prefix="/api")
app.include_router(config_routes.router, prefix="/api")
app.include_router(market_data.router)

# WebSocket
app.add_api_websocket_route("/ws", ws_endpoint)

# Static files (HTMX frontend)
_web_dir = os.path.join(os.path.dirname(__file__), "..", "..", "web")
if os.path.isdir(_web_dir):
    app.mount("/static", StaticFiles(directory=_web_dir), name="static")

    @app.get("/")
    async def serve_dashboard():
        return FileResponse(os.path.join(_web_dir, "index.html"))
