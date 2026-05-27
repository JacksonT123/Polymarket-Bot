"""Unified execution: same CLOB book pricing for PAPER and LIVE."""
from __future__ import annotations

from bot.config import get_settings
from bot.exec.clob_book import fetch_order_book, plan_fill_from_book
from bot.exec.live import post_live_order
from bot.ledger import repo
from bot.models import CopyIntent, DecisionCode


async def execute_copy(intent: CopyIntent) -> dict | None:
    cfg = get_settings()

    book = await fetch_order_book(intent.token_id)
    if not book:
        return {"status": "rejected", "reason": "no_book", "code": str(DecisionCode.SKIP_MARKET_ILLQUID)}

    price, shares, reason = plan_fill_from_book(intent, book)
    if reason or shares <= 0:
        return {"status": "rejected", "reason": reason or "no_fill", "code": str(DecisionCode.SKIP_MARKET_ILLQUID)}

    sized = CopyIntent(
        event_id=intent.event_id,
        leader_proxy=intent.leader_proxy,
        condition_id=intent.condition_id,
        token_id=intent.token_id,
        side=intent.side,
        target_notional=shares * price,
        target_shares=shares,
        limit_price=price,
        leader_fraction=intent.leader_fraction,
        sizing_details=intent.sizing_details,
    )

    if cfg.is_live:
        if not cfg.live_ready:
            return {"status": "rejected", "reason": "missing_credentials", "code": str(DecisionCode.SKIP_LIVE_DISABLED)}
        result = await post_live_order(sized, price, shares)
        if result is None:
            return None
        if result.get("status") == "filled":
            await repo.apply_fill(
                sized, price, shares, mode="LIVE", exchange_order_id=str(result.get("exchange_order_id") or "")
            )
        return result

    await repo.apply_fill(sized, price, shares, mode="PAPER", exchange_order_id="")
    return {"status": "filled", "mode": "PAPER", "fill_price": price, "shares": shares, "notional": shares * price}
