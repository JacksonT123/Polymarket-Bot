"""GET /api/state — top-level bot status, equity, metrics."""
from __future__ import annotations

from fastapi import APIRouter

from bot.config import get_settings
from bot.ledger import repo
from bot.observability.metrics import get_topline

router = APIRouter()


@router.get("")
async def get_state() -> dict:
    cfg = get_settings()
    metrics = await get_topline(cfg.bot_mode)
    ks = await repo.get_kill_switch()

    return {
        "mode": cfg.bot_mode,
        "kill_switch_triggered": bool(ks.get("triggered")),
        "kill_switch_reason": ks.get("reason"),
        "equity_usd": metrics.equity_usd,
        "cash_usd": metrics.cash_usd,
        "open_positions_usd": metrics.open_positions_usd,
        "realized_pnl_usd": metrics.realized_pnl_usd,
        "unrealized_pnl_usd": metrics.unrealized_pnl_usd,
        "total_trades": metrics.total_trades,
        "win_rate": metrics.win_rate,
        "paper_gate_passed": metrics.paper_gate_passed,
        "daily_loss_usd": metrics.daily_loss_usd,
        "fill_rate": metrics.fill_rate,
    }
