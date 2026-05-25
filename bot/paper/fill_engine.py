"""
Paper fill engine: pessimistic FOK simulator.
- BUY: fills at leader_price + 0.5¢ VWAP nudge
- SELL: fills at leader_price - 0.5¢ VWAP nudge
- 25% depth haircut — if requested shares > 75% of available depth → REJECTED
- Fee: 2¢ per $100 notional (0.02%)
"""
from __future__ import annotations

import time
import uuid

from bot.models import FillResult, OrderIntent, OrderSide, OrderStatus
from bot.observability.log import get_logger
from bot.paper.book_cache import available_depth, get_book_for_fill

log = get_logger(__name__)

_VWAP_NUDGE = 0.005   # 0.5¢
_DEPTH_HAIRCUT = 0.75  # only 75% of book depth is usable
_FEE_RATE = 0.0002     # 0.02%
_MIN_FILL_PRICE = 0.01
_MAX_FILL_PRICE = 0.99


async def simulate_fill(intent: OrderIntent) -> FillResult | None:
    """
    Simulate FOK fill for a paper order.
    Returns FillResult with FILLED or REJECTED status.
    """
    book = get_book_for_fill(intent.token_id, intent.side, intent.limit_price)

    # Compute fill price with VWAP nudge (adverse to us — pessimistic)
    if intent.side == OrderSide.BUY:
        fill_price = min(_MAX_FILL_PRICE, intent.limit_price + _VWAP_NUDGE)
    else:
        fill_price = max(_MIN_FILL_PRICE, intent.limit_price - _VWAP_NUDGE)

    # Depth check
    depth = available_depth(book, intent.side, intent.limit_price)
    usable_depth = depth * _DEPTH_HAIRCUT

    if intent.size_shares > usable_depth:
        log.info(
            "paper_fill_rejected_depth",
            market=intent.condition_id[:12],
            requested=intent.size_shares,
            usable_depth=usable_depth,
        )
        return FillResult(
            client_order_id=intent.client_order_id,
            exchange_order_id=None,
            status=OrderStatus.REJECTED,
            filled_shares=0.0,
            avg_price=0.0,
            fee_usd=0.0,
            filled_at_ts=int(time.time()),
            reject_reason="insufficient_depth",
        )

    # Notional and fee
    notional = intent.size_shares * fill_price
    fee_usd = notional * _FEE_RATE

    log.info(
        "paper_fill_accepted",
        market=intent.condition_id[:12],
        side=intent.side.value,
        shares=intent.size_shares,
        fill_price=fill_price,
        notional=notional,
        fee=fee_usd,
    )

    return FillResult(
        client_order_id=intent.client_order_id,
        exchange_order_id=f"paper_{uuid.uuid4().hex[:16]}",
        status=OrderStatus.FILLED,
        filled_shares=intent.size_shares,
        avg_price=fill_price,
        fee_usd=fee_usd,
        filled_at_ts=int(time.time()),
        reject_reason=None,
    )
