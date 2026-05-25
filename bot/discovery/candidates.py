"""
Step 1 of discovery funnel: pull candidate wallets from all sources
and produce a deduplicated union of proxy addresses.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from bot.data.data_api import DataAPIClient
from bot.data.subgraphs import get_wallet_pnl
from bot.observability.log import get_logger

log = get_logger(__name__)

_LEADERBOARD_WINDOWS = [
    ("OVERALL", "DAY"),
    ("OVERALL", "WEEK"),
    ("OVERALL", "MONTH"),
    ("POLITICS", "WEEK"),
    ("SPORTS", "WEEK"),
    ("CRYPTO", "WEEK"),
]


async def gather_candidates(client: DataAPIClient) -> set[str]:
    """
    Pull up to ~1,500 candidate proxy addresses from:
    - Data API leaderboard (multiple categories × time windows)
    - Goldsky pnl-subgraph (30d realized PnL ranking)

    Returns a set of proxy wallet addresses.
    """
    proxies: set[str] = set()
    since_30d = int((datetime.now(tz=timezone.utc) - timedelta(days=30)).timestamp())

    tasks = [
        _fetch_leaderboard(client, cat, period)
        for cat, period in _LEADERBOARD_WINDOWS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            log.warning("leaderboard_fetch_error", error=str(r))
            continue
        proxies.update(r)

    log.info("candidates_gathered", total=len(proxies))
    return proxies


async def _fetch_leaderboard(
    client: DataAPIClient, category: str, period: str
) -> set[str]:
    all_wallets = await client.get_all_leaderboard_pages(
        category=category, time_period=period, order_by="PNL", max_offset=500
    )
    proxies = {w["proxyWallet"] for w in all_wallets if w.get("proxyWallet")}
    log.info(
        "leaderboard_fetched",
        category=category,
        period=period,
        count=len(proxies),
    )
    return proxies
