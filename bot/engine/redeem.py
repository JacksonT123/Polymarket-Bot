import asyncio

from bot.config import get_settings
from bot.exec.clob_book import fetch_order_book
from bot.exec.executor import execute_copy
from bot.ledger import repo
from bot.models import CopyIntent, Side
from bot.observability.log import get_logger

log = get_logger(__name__)


async def redeem_resolved_positions() -> int:
    positions = await repo.get_positions()
    redeemed = 0
    cfg = get_settings()
    gap = cfg.clob_min_interval_ms / 1000.0
    for p in positions:
        token_id = str(p["token_id"])
        book = await fetch_order_book(token_id)
        if not book:
            continue
        bids = book.get("bids") or []
        asks = book.get("asks") or []
        try:
            best_bid = float(bids[0]["price"]) if bids else 0.0
            best_ask = float(asks[0]["price"]) if asks else 1.0
        except (KeyError, TypeError, ValueError):
            continue
        mid = (best_bid + best_ask) / 2 if best_bid and best_ask else best_bid or best_ask
        if 0.03 < mid < 0.97:
            continue
        shares = float(p["shares"])
        if shares <= 0:
            continue
        intent = CopyIntent(
            event_id=f"redeem:{p['condition_id']}:{token_id}",
            leader_proxy=str(p.get("leader_proxy") or ""),
            condition_id=p["condition_id"],
            token_id=token_id,
            side=Side.SELL,
            target_notional=shares * mid,
            target_shares=shares,
            limit_price=mid,
        )
        fill = await execute_copy(intent)
        if fill and fill.get("status") == "filled":
            redeemed += 1
            log.info("position_redeemed", condition=p["condition_id"][:12], price=mid, mode=fill.get("mode"))
        await asyncio.sleep(gap)
    return redeemed
