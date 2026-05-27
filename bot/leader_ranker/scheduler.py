from __future__ import annotations

import asyncio

from bot.config import get_settings
from bot.data.client import DataAPIClient
from bot.leader_ranker.pipeline import run_discovery
from bot.observability.log import get_logger

log = get_logger(__name__)


async def discovery_scheduler(stop: asyncio.Event) -> None:
    cfg = get_settings()
    interval = max(60.0, cfg.discovery_interval_hours * 3600)
    client = DataAPIClient()
    try:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
            if stop.is_set():
                break
            try:
                log.info("discovery_scheduler_run")
                await run_discovery(client)
            except Exception as e:
                log.error("discovery_scheduler_error", error=str(e))
    finally:
        await client.close()
