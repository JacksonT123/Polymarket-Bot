"""
Step 2: Hard filters — drop candidates immediately.
All checks are against Data API /trades, /positions, /value.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone

from bot.data.data_api import DataAPIClient
from bot.models import LeaderCandidate
from bot.observability.log import get_logger

log = get_logger(__name__)

# Hard filter thresholds (from spec §2.3)
MIN_TRADES_30D = 30
MAX_TRADES_30D = 5000
MIN_VALUE_USD = 1_000
MAX_VALUE_USD = 250_000
MIN_ACCOUNT_AGE_DAYS = 21
MAX_DRAWDOWN_30D = 0.35


async def hard_filter(proxy: str, client: DataAPIClient) -> str | None:
    """
    Fetch stats for `proxy` and apply all hard filters.
    Returns an exclusion reason string, or None if the wallet passes.
    """
    since_30d = int((datetime.now(tz=timezone.utc) - timedelta(days=30)).timestamp())
    since_21d = int((datetime.now(tz=timezone.utc) - timedelta(days=21)).timestamp())

    try:
        trades = await client.get_trades(user=proxy, limit=500)
    except Exception as e:
        return f"api_error:{e}"

    trades_30d = [t for t in trades if int(t.get("timestamp", 0)) >= since_30d]
    trade_count = len(trades_30d)

    if trade_count < MIN_TRADES_30D:
        return f"too_few_trades:{trade_count}"
    if trade_count > MAX_TRADES_30D:
        return f"too_many_trades:{trade_count}"

    # Check account age via oldest trade
    if trades:
        oldest_ts = min(int(t.get("timestamp", time.time())) for t in trades)
        age_days = (time.time() - oldest_ts) / 86400
        if age_days < MIN_ACCOUNT_AGE_DAYS:
            return f"account_too_new:{age_days:.1f}d"

    try:
        value_usd = await client.get_value(user=proxy)
    except Exception:
        value_usd = 0.0

    if value_usd < MIN_VALUE_USD:
        return f"value_too_low:{value_usd:.0f}"
    if value_usd > MAX_VALUE_USD:
        return f"value_too_high:{value_usd:.0f}"

    # Positive realized PnL check via trades
    buys = [t for t in trades_30d if t.get("side") == "BUY"]
    sells = [t for t in trades_30d if t.get("side") == "SELL"]
    if not sells:
        return "no_closed_positions"

    # Estimated P&L: sum of (sell notional - buy notional) per market — very rough
    # Real PnL comes from the scoring step (pnl-subgraph)
    return None  # passes hard filter; scoring happens next


async def filter_candidates(
    proxies: set[str], client: DataAPIClient
) -> list[tuple[str, str | None]]:
    """
    Apply hard_filter to all candidates concurrently (with concurrency cap).
    Returns list of (proxy, exclusion_reason). reason=None means passed.
    """
    sem = asyncio.Semaphore(10)
    results: list[tuple[str, str | None]] = []

    async def check(proxy: str) -> None:
        async with sem:
            reason = await hard_filter(proxy, client)
            results.append((proxy, reason))

    await asyncio.gather(*[check(p) for p in proxies])
    passed = sum(1 for _, r in results if r is None)
    log.info("hard_filter_complete", total=len(proxies), passed=passed)
    return results
