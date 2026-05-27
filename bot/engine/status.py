"""In-memory engine heartbeat for dashboard."""
from __future__ import annotations

import time

from bot.data.coordinator import discovery_active

_stats: dict = {
    "last_poll_at": 0.0,
    "last_copy_at": 0.0,
    "poll_cycles": 0,
    "events_seen": 0,
    "api_errors": 0,
    "last_error": "",
    "started_at": time.time(),
}


def record_poll(*, leaders: int, events: int) -> None:
    _stats["last_poll_at"] = time.time()
    _stats["poll_cycles"] += 1
    _stats["leaders_polled"] = leaders
    _stats["events_seen"] += events
    if leaders > 0 and _stats["api_errors"] > 0:
        _stats["api_errors"] = max(0, _stats["api_errors"] - 1)


def record_copy() -> None:
    _stats["last_copy_at"] = time.time()


def record_api_error(msg: str) -> None:
    _stats["api_errors"] += 1
    _stats["last_error"] = msg[:200]


def snapshot() -> dict:
    from bot.data import rate_limit

    now = time.time()
    last_poll = _stats["last_poll_at"]
    last_copy = _stats["last_copy_at"]
    cooldown = rate_limit.cooldown_remaining()
    return {
        **_stats,
        "seconds_since_poll": int(now - last_poll) if last_poll else None,
        "seconds_since_copy": int(now - last_copy) if last_copy else None,
        "uptime_sec": int(now - _stats["started_at"]),
        "rate_limit_cooldown_sec": round(cooldown, 1),
        "rate_limit_hits": rate_limit.rate_limit_hits(),
        "discovery_running": discovery_active(),
    }
