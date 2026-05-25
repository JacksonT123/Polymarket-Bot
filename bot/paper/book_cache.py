"""
Book cache for paper trading: wraps the live order book WebSocket data
and provides a simple interface for the fill engine to query depth.
Falls back to synthetic depth when no live book is available.
"""
from __future__ import annotations

from bot.clob.ws_market import get_book
from bot.models import BookLevel, OrderBook, OrderSide
from bot.observability.log import get_logger

log = get_logger(__name__)

_SYNTHETIC_DEPTH_LEVELS = 5
_SYNTHETIC_SPREAD = 0.01  # 1¢ between levels
_SYNTHETIC_SIZE_PER_LEVEL = 200.0  # $200 per level


def get_book_for_fill(token_id: str, side: OrderSide, limit_price: float) -> OrderBook | None:
    """
    Returns the order book for fill simulation.
    Uses live WebSocket data if available; falls back to synthetic book.
    """
    book = get_book(token_id)
    if book is not None:
        return book

    log.debug("book_cache_synthetic", token_id=token_id[:12])
    return _synthetic_book(limit_price, side)


def _synthetic_book(mid_price: float, side: OrderSide) -> OrderBook:
    """
    Build a synthetic order book around mid_price for paper fill simulation.
    Used when no live book is available (e.g., market not yet subscribed).
    """
    mid = max(0.01, min(0.99, mid_price))

    # Asks above mid, bids below mid
    asks: list[BookLevel] = []
    bids: list[BookLevel] = []

    for i in range(_SYNTHETIC_DEPTH_LEVELS):
        ask_price = round(min(0.99, mid + _SYNTHETIC_SPREAD * (i + 1)), 4)
        bid_price = round(max(0.01, mid - _SYNTHETIC_SPREAD * (i + 1)), 4)
        size = _SYNTHETIC_SIZE_PER_LEVEL / ask_price  # convert $ to shares

        asks.append(BookLevel(price=ask_price, size=size))
        bids.append(BookLevel(price=bid_price, size=size))

    return OrderBook(
        token_id="synthetic",
        bids=bids,
        asks=asks,
        timestamp=0,
    )


def available_depth(book: OrderBook, side: OrderSide, limit_price: float) -> float:
    """
    Total shares available up to limit_price on the relevant side.
    BUY → take from asks up to limit_price.
    SELL → take from bids down to limit_price.
    """
    if side == OrderSide.BUY:
        levels = [l for l in (book.asks or []) if l.price <= limit_price]
    else:
        levels = [l for l in (book.bids or []) if l.price >= limit_price]

    return sum(l.size for l in levels)
