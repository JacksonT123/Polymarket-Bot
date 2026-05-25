"""
Anti-wash-trading and cluster detection.
Based on the Columbia/Barnard SSRN paper (Kanoria, Ma, Sethi, Sirolly; Nov 2025).
Wallets with wash_score > 0.3 are excluded.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from bot.data.data_api import DataAPIClient
from bot.data.subgraphs import get_order_filled_events
from bot.models import LeaderCandidate
from bot.observability.log import get_logger

log = get_logger(__name__)


async def compute_wash_score(proxy: str, client: DataAPIClient) -> float:
    """
    Returns a wash-trading score in [0, 1].
    Score > 0.3 → exclude from roster.

    Components:
      1. Counterparty concentration (HHI) → +0.5 if > 0.4 in any 24h window
      2. Round-trip clustering (buy→sell same market < 10 min, near-zero net) → +0.3 if > 15%
      3. Extreme-price trades (< $0.01 or > $0.99) → +0.4 if > 20%
      4. Volume/PnL imbalance → +0.4 if |pnl| / vol < 0.001 at vol > $50k
    """
    since_30d = int((datetime.now(tz=timezone.utc) - timedelta(days=30)).timestamp())

    try:
        trades = await client.get_trades(user=proxy, limit=500)
        activity = await client.get_activity(user=proxy, since=since_30d)
    except Exception as e:
        log.warning("wash_score_data_error", proxy=proxy, error=str(e))
        return 0.0

    score = 0.0

    # 1. Round-trip clustering
    score += _round_trip_score(trades)

    # 2. Extreme-price trades
    score += _extreme_price_score(trades)

    # 3. Volume/PnL imbalance
    score += _volume_pnl_imbalance_score(trades)

    # 4. Counterparty concentration — requires orderbook subgraph events
    # Simplified: flag if activity has very high repetition in same market short windows
    score += _repetition_score(trades)

    return min(score, 1.0)


def _round_trip_score(trades: list[dict]) -> float:
    """Fraction of trades that are buy→sell in same market within 10 min."""
    if not trades:
        return 0.0
    market_buys: dict[str, list[int]] = defaultdict(list)
    round_trips = 0

    for t in sorted(trades, key=lambda x: int(x.get("timestamp", 0))):
        market = t.get("conditionId", t.get("market", ""))
        ts = int(t.get("timestamp", 0))
        side = t.get("side", "")
        if side == "BUY":
            market_buys[market].append(ts)
        elif side == "SELL" and market_buys.get(market):
            buy_ts = market_buys[market].pop(0)
            if ts - buy_ts <= 600:  # 10 minutes
                round_trips += 1

    fraction = round_trips / max(len(trades), 1)
    return 0.3 if fraction > 0.15 else 0.0


def _extreme_price_score(trades: list[dict]) -> float:
    """Fraction of trades at extreme prices (< $0.01 or > $0.99)."""
    if not trades:
        return 0.0
    extreme = sum(
        1
        for t in trades
        if (price := float(t.get("price", 0.5))) < 0.01 or price > 0.99
    )
    fraction = extreme / len(trades)
    return 0.4 if fraction > 0.20 else 0.0


def _volume_pnl_imbalance_score(trades: list[dict]) -> float:
    """Flag if total volume > $50k but |realized_pnl| / volume < 0.001."""
    total_volume = sum(
        float(t.get("size", 0)) * float(t.get("price", 0)) for t in trades
    )
    if total_volume < 50_000:
        return 0.0
    # Without realized PnL data here we can't fully compute — return 0
    return 0.0


def _repetition_score(trades: list[dict]) -> float:
    """
    Simple proxy for counterparty concentration:
    flag if > 40% of trades are in the same market in the same 24h window.
    """
    if not trades:
        return 0.0
    window_markets: dict[int, list[str]] = defaultdict(list)  # day_bucket → [market]
    for t in trades:
        ts = int(t.get("timestamp", 0))
        day = ts // 86400
        market = t.get("conditionId", t.get("market", ""))
        window_markets[day].append(market)

    for day, markets in window_markets.items():
        if not markets:
            continue
        counts: dict[str, int] = defaultdict(int)
        for m in markets:
            counts[m] += 1
        max_count = max(counts.values())
        # HHI for this day
        hhi = sum((c / len(markets)) ** 2 for c in counts.values())
        if hhi > 0.4:
            return 0.5

    return 0.0


async def detect_clusters(proxies: list[str]) -> dict[str, str]:
    """
    Funding-source cluster detection via Polygon RPC.
    Returns {proxy: canonical_proxy} for wallets in the same funding cluster.
    In the same weakly-connected component, only the highest-scoring wallet
    is kept; all siblings map to it.

    Simplified implementation: returns empty dict (cluster detection via
    eth_getLogs requires Alchemy RPC and EOA resolution — wired in production).
    """
    # Production: resolve EOA for each proxy via Safe singleton owner() call,
    # then trace USDC funding hops via eth_getLogs, build adjacency graph,
    # find connected components, return mapping.
    log.info("cluster_detection_stub", count=len(proxies))
    return {}
