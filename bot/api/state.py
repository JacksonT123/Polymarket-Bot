import time

from bot.config import get_settings
from bot.engine import status as engine_status
from bot.ledger import repo
from bot.portfolio.mtm import enrich_positions


async def build_state_payload(*, force_mtm: bool = False) -> dict:
    acct = await repo.get_account_state()
    cfg = get_settings()
    starting = float(acct.get("starting_equity_usd") or cfg.starting_bankroll_usd)
    cash = float(acct.get("cash_usd") or 0)
    realized = await repo.get_total_realized_pnl()

    try:
        positions_raw = await repo.get_positions()
    except Exception:
        positions_raw = []

    max_age = 0.0 if force_mtm else cfg.mtm_cache_seconds
    positions, mtm_meta = await enrich_positions(positions_raw, max_age_sec=max_age)

    live_equity = cash + mtm_meta["positions_mtm_usd"]
    cost_equity = cash + mtm_meta["positions_cost_usd"]
    unrealized = mtm_meta["unrealized_pnl_usd"]
    live_pnl = live_equity - starting

    try:
        metrics = await repo.get_metrics()
    except Exception:
        metrics = {"fills": 0, "skip_by_code": {}}
    summary = await repo.get_decision_summary(since_ts=int(time.time()) - 3600)
    open_markets = await repo.count_open_markets()
    kill = await repo.is_kill_switch_active()

    return {
        "account": {**acct, "equity_usd": live_equity, "cost_equity_usd": cost_equity},
        "cash_usd": cash,
        "invested_usd": mtm_meta["positions_cost_usd"],
        "invested_mtm_usd": mtm_meta["positions_mtm_usd"],
        "unrealized_pnl_usd": unrealized,
        "realized_pnl_usd": realized,
        "open_markets": open_markets,
        "kill_switch": kill,
        "pnl_usd": live_pnl,
        "pnl_pct": (live_pnl / starting * 100) if starting else 0,
        "leaders": await repo.get_leaders(status="active"),
        "standby": await repo.get_leaders(status="standby"),
        "positions": positions,
        "fills_recent": await repo.get_recent_fills(30),
        "leader_pnl": await repo.get_leader_pnl(),
        "discovery": await repo.get_last_discovery(),
        "metrics": metrics,
        "summary_1h": summary,
        "recent": await repo.get_recent_decisions(limit=100),
        "engine": engine_status.snapshot(),
        "updated_at": int(time.time()),
        "config": {
            "mode": cfg.bot_mode,
            "auto_discover": cfg.auto_discover_leaders,
            "roster_active": cfg.roster_active_size,
            "poll_seconds": cfg.activity_poll_seconds,
            "ws_interval_ms": cfg.dashboard_ws_interval_ms,
            "live_ready": cfg.live_ready,
            "max_open_markets": cfg.max_open_markets,
            "min_copy_usd": cfg.min_copy_for_mode,
        },
    }
