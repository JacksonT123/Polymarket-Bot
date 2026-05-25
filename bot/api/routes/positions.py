"""GET /api/positions — open and closed positions."""
from __future__ import annotations

from fastapi import APIRouter, Query

from bot.config import get_settings
from bot.ledger import repo

router = APIRouter()


@router.get("/open")
async def get_open_positions(mode: str | None = None) -> list[dict]:
    cfg = get_settings()
    m = mode or cfg.bot_mode
    return await repo.get_open_positions(m)


@router.get("/closed")
async def get_closed_positions(
    mode: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
) -> list[dict]:
    cfg = get_settings()
    m = mode or cfg.bot_mode
    return await repo.get_closed_positions(m, limit=limit, offset=offset)


@router.get("/pnl")
async def get_pnl_curve(mode: str | None = None) -> list[dict]:
    """Equity curve data points for chart rendering."""
    cfg = get_settings()
    m = mode or cfg.bot_mode
    return await repo.get_equity_snapshots(m, limit=500)
