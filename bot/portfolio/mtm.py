"""Mark open positions to market via CLOB (same book as execution)."""
from __future__ import annotations

import asyncio
import time

from bot.exec.clob_book import fetch_order_book

_cache: dict[str, tuple[float, float]] = {}
_cache_ts = 0.0
_lock = asyncio.Lock()


def _mid_from_book(book: dict) -> float | None:
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    try:
        best_bid = float(bids[0]["price"]) if bids else 0.0
        best_ask = float(asks[0]["price"]) if asks else 1.0
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    if best_bid and best_ask:
        return (best_bid + best_ask) / 2
    return best_bid or best_ask or None


async def _price_for_token(token_id: str) -> float | None:
    if not token_id:
        return None
    book = await fetch_order_book(token_id)
    if not book:
        return None
    return _mid_from_book(book)


async def enrich_positions(positions: list[dict], *, max_age_sec: float = 2.0) -> tuple[list[dict], dict]:
    """
    Returns (positions with mark_price/mtm/unrealized_pnl, totals).
    Reuses in-memory cache younger than max_age_sec.
    """
    global _cache_ts
    now = time.monotonic()
    async with _lock:
        stale = (now - _cache_ts) > max_age_sec
        if stale:
            _cache.clear()
            for p in positions:
                tid = str(p.get("token_id") or "")
                mid = await _price_for_token(tid)
                if mid is not None:
                    _cache[tid] = (mid, now)
            _cache_ts = now

    enriched: list[dict] = []
    mtm_total = 0.0
    cost_total = 0.0
    unrealized = 0.0
    for p in positions:
        shares = float(p["shares"])
        avg = float(p["avg_price"])
        cost = shares * avg
        tid = str(p.get("token_id") or "")
        mid = _cache.get(tid, (avg, now))[0]
        mtm = shares * mid
        upnl = mtm - cost
        row = {**p, "mark_price": mid, "cost_usd": cost, "mtm_usd": mtm, "unrealized_pnl": upnl}
        enriched.append(row)
        mtm_total += mtm
        cost_total += cost
        unrealized += upnl

    return enriched, {
        "positions_mtm_usd": mtm_total,
        "positions_cost_usd": cost_total,
        "unrealized_pnl_usd": unrealized,
    }


def invalidate_cache() -> None:
    global _cache_ts
    _cache.clear()
    _cache_ts = 0.0
