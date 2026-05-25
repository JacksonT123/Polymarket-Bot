"""
FOK order builder helpers.
Computes the FOK limit price: leader_price ± N ticks, clamped to book and [0.01, 0.99].
"""
from __future__ import annotations

import hashlib

from bot.config import get_settings
from bot.models import OrderBook, OrderIntent, OrderSide


def build_client_order_id(
    condition_id: str,
    token_id: str,
    outcome: str,
    price: float,
    size: float,
) -> str:
    """Deterministic 16-char hex ID — idempotent on crash/retry."""
    key = f"{condition_id}:{token_id}:{outcome}:{price:.4f}:{size:.2f}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def compute_fok_price(
    leader_price: float,
    side: OrderSide,
    book: OrderBook,
    tick_size: float = 0.01,
) -> float:
    cfg = get_settings()
    n = cfg.fok_tick_buffer

    if side == OrderSide.BUY:
        price = leader_price + n * tick_size
        ask = book.best_ask() if book else None
        if ask is not None:
            price = min(price, ask)
        price = min(price, 0.99)
    else:
        price = leader_price - n * tick_size
        bid = book.best_bid() if book else None
        if bid is not None:
            price = max(price, bid)
        price = max(price, 0.01)

    price = round(round(price / tick_size) * tick_size, 6)
    return price


def build_order_intent(
    condition_id: str,
    token_id: str,
    outcome: str,
    side: OrderSide,
    leader_price: float,
    size_shares: float,
    book: OrderBook | None,
    signal_ids: list[str],
    leader_ranks: list[int],
    tick_size: float = 0.01,
) -> OrderIntent | None:
    """Build an OrderIntent. Returns None if size_shares is effectively zero."""
    if size_shares < 1.0:
        return None

    fok_price = compute_fok_price(
        leader_price=leader_price,
        side=side,
        book=book or _empty_book(leader_price),
        tick_size=tick_size,
    )

    coid = build_client_order_id(condition_id, token_id, outcome, fok_price, size_shares)

    return OrderIntent(
        condition_id=condition_id,
        token_id=token_id,
        outcome=outcome,
        side=side,
        limit_price=fok_price,
        size_shares=size_shares,
        client_order_id=coid,
        signal_ids=signal_ids,
        leader_ranks=leader_ranks,
    )


def _empty_book(mid: float) -> OrderBook:
    from bot.models import BookLevel
    return OrderBook(
        token_id="",
        bids=[BookLevel(price=max(0.01, mid - 0.01), size=0)],
        asks=[BookLevel(price=min(0.99, mid + 0.01), size=0)],
        timestamp=0,
    )
