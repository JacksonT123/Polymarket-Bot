from __future__ import annotations

import asyncio
import time

import certifi
import httpx

from bot.config import get_settings

_clob_lock = asyncio.Lock()
_clob_last_at = 0.0
_clob_http: httpx.AsyncClient | None = None


async def _clob_client() -> httpx.AsyncClient:
    global _clob_http
    if _clob_http is None:
        cfg = get_settings()
        verify: bool | str = certifi.where() if cfg.ssl_verify else False
        _clob_http = httpx.AsyncClient(timeout=12.0, verify=verify)
    return _clob_http


async def fetch_order_book(token_id: str) -> dict | None:
    global _clob_last_at
    if not token_id:
        return None
    cfg = get_settings()
    interval = max(0.15, cfg.clob_min_interval_ms / 1000.0)
    async with _clob_lock:
        now = time.monotonic()
        wait = _clob_last_at + interval - now
        if wait > 0:
            await asyncio.sleep(wait)
        _clob_last_at = time.monotonic()
        http = await _clob_client()
        try:
            r = await http.get(f"{cfg.clob_base_url}/book", params={"token_id": token_id})
            r.raise_for_status()
            return r.json()
        except Exception:
            return None


def _walk_levels(levels: list, need_shares: float) -> tuple[float, float]:
    filled = 0.0
    cost = 0.0
    for lvl in levels:
        try:
            price = float(lvl.get("price", 0))
            size = float(lvl.get("size", 0))
        except (TypeError, ValueError):
            continue
        if price <= 0 or size <= 0:
            continue
        take = min(size, need_shares - filled)
        if take <= 0:
            break
        filled += take
        cost += take * price
        if filled >= need_shares - 1e-9:
            break
    if filled <= 0:
        return 0.0, 0.0
    return cost / filled, filled


def plan_fill_from_book(intent, book: dict) -> tuple[float, float, str | None]:
    from bot.models import Side

    cfg = get_settings()
    slip = cfg.paper_slippage_cents / 100.0
    need = intent.target_shares

    if intent.side == Side.BUY:
        asks = book.get("asks") or []
        vwap, filled = _walk_levels(asks, need)
        if filled <= 0:
            return 0.0, 0.0, "no_ask_liquidity"
        price = min(0.99, vwap + slip)
    else:
        bids = book.get("bids") or []
        vwap, filled = _walk_levels(bids, need)
        if filled <= 0:
            return 0.0, 0.0, "no_bid_liquidity"
        price = max(0.01, vwap - slip)

    haircut = cfg.paper_depth_haircut if not cfg.is_live else 1.0
    fillable = min(need, filled * haircut)
    if fillable * price < cfg.min_copy_for_mode * 0.99:
        return price, fillable, "below_min_after_depth"
    return price, fillable, None
