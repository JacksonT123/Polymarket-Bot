"""Shared throttle for all Polymarket Data API clients in this process."""
from __future__ import annotations

import asyncio
import time

from bot.config import get_settings

_lock = asyncio.Lock()
_last_request_at = 0.0
_cooldown_until = 0.0
_rate_limit_hits = 0
_consecutive_ok = 0


async def wait_turn() -> None:
    global _last_request_at
    cfg = get_settings()
    interval = cfg.data_api_min_interval_ms / 1000.0
    async with _lock:
        now = time.monotonic()
        if now < _cooldown_until:
            await asyncio.sleep(_cooldown_until - now)
            now = time.monotonic()
        wait = _last_request_at + interval - now
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_at = time.monotonic()


def penalize_429(attempt: int) -> float:
    global _cooldown_until, _rate_limit_hits, _consecutive_ok
    _rate_limit_hits += 1
    _consecutive_ok = 0
    pause = min(3.0 * (2**attempt), 45.0)
    until = time.monotonic() + pause
    if until > _cooldown_until:
        _cooldown_until = until
    return pause


def cooldown_remaining() -> float:
    return max(0.0, _cooldown_until - time.monotonic())


def rate_limit_hits() -> int:
    return _rate_limit_hits


def note_success() -> None:
    global _consecutive_ok, _rate_limit_hits
    _consecutive_ok += 1
    if _consecutive_ok >= 20 and _rate_limit_hits > 0:
        _rate_limit_hits = max(0, _rate_limit_hits - 5)
        _consecutive_ok = 0


def reset_stats() -> None:
    global _rate_limit_hits, _consecutive_ok
    _rate_limit_hits = 0
    _consecutive_ok = 0
