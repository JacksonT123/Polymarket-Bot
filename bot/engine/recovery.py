"""
Crash recovery: on startup, reconcile in-flight orders and open positions
against actual on-chain / CLOB state so the ledger stays accurate.
"""
from __future__ import annotations

import time

from bot.data.data_api import DataAPIClient
from bot.ledger import repo
from bot.models import OrderStatus
from bot.observability.log import get_logger

log = get_logger(__name__)

_STALE_ORDER_SECONDS = 300  # 5 minutes — FOK orders should resolve instantly


async def reconcile_on_startup(client: DataAPIClient, mode: str) -> None:
    """
    Called once at bot startup before starting the engine loop.
    Steps:
      1. Mark any PENDING orders older than 5 min as EXPIRED
      2. Re-sync open positions against Data API current positions
      3. Snapshot equity
    """
    log.info("recovery_start", mode=mode)

    await _expire_stale_orders(mode)
    await _sync_positions(client, mode)
    await _snapshot_equity(mode)

    log.info("recovery_complete", mode=mode)


async def _expire_stale_orders(mode: str) -> None:
    """FOK orders either fill or reject immediately — anything PENDING after 5 min is stuck."""
    cutoff = int(time.time()) - _STALE_ORDER_SECONDS
    count = await repo.expire_stale_orders(cutoff, mode)
    if count:
        log.warning("recovery_expired_orders", count=count, mode=mode)


async def _sync_positions(client: DataAPIClient, mode: str) -> None:
    """
    For LIVE mode only: compare ledger open positions against Data API.
    Close any positions that were closed externally while bot was down.
    Paper mode doesn't need this — it has no on-chain state.
    """
    if mode != "LIVE":
        return

    ledger_positions = await repo.get_open_positions(mode)
    if not ledger_positions:
        return

    cfg_proxy = None
    try:
        from bot.config import get_settings
        cfg_proxy = get_settings().proxy_wallet
    except Exception:
        pass

    if not cfg_proxy:
        log.warning("recovery_no_proxy_wallet")
        return

    try:
        api_positions = await client.get_positions(user=cfg_proxy, limit=500, sort_by="CURRENT")
        api_open_markets = {
            p.get("conditionId", "") for p in api_positions if float(p.get("size", 0)) > 0
        }
    except Exception as e:
        log.error("recovery_api_error", error=str(e))
        return

    for pos in ledger_positions:
        if pos["condition_id"] not in api_open_markets:
            log.warning(
                "recovery_position_missing_on_chain",
                condition_id=pos["condition_id"][:12],
            )
            # Mark as closed externally with zero realized PnL recorded
            await repo.mark_position_externally_closed(
                condition_id=pos["condition_id"],
                token_id=pos["token_id"],
                mode=mode,
            )


async def _snapshot_equity(mode: str) -> None:
    """Take an equity snapshot at startup."""
    try:
        from bot.observability.metrics import get_topline
        metrics = await get_topline(mode)
        await repo.insert_equity_snapshot(
            equity_usd=metrics.equity_usd,
            cash_usd=metrics.cash_usd,
            positions_usd=metrics.open_positions_usd,
            mode=mode,
        )
    except Exception as e:
        log.warning("recovery_snapshot_error", error=str(e))
