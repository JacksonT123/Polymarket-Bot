"""Coordinates discovery vs copy polling so they never hammer the API together."""
from __future__ import annotations

import asyncio

_discovery_lock = asyncio.Lock()
_discovery_running = False


def discovery_active() -> bool:
    return _discovery_running


async def wait_until_not_discovering(poll_interval: float = 0.5) -> None:
    while _discovery_running:
        await asyncio.sleep(poll_interval)


async def run_discovery_guarded(fn):
    global _discovery_running
    async with _discovery_lock:
        _discovery_running = True
        try:
            return await fn()
        finally:
            _discovery_running = False
