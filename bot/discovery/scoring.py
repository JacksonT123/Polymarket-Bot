"""
Step 3: Scoring — exact formula from spec §2.4.
Percentile-normalizes each metric within the candidate pool, then computes
a weighted composite score.
"""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from bot.data.data_api import DataAPIClient
from bot.data.subgraphs import get_wallet_pnl
from bot.models import LeaderCandidate
from bot.observability.log import get_logger

log = get_logger(__name__)


async def compute_candidate_stats(
    proxy: str, client: DataAPIClient
) -> LeaderCandidate | None:
    """Fetch all metrics needed for scoring."""
    since_30d = int((datetime.now(tz=timezone.utc) - timedelta(days=30)).timestamp())
    since_7d = int((datetime.now(tz=timezone.utc) - timedelta(days=7)).timestamp())

    try:
        trades_all = await client.get_trades(user=proxy, limit=500)
        positions = await client.get_positions(user=proxy, limit=200, sort_by="CURRENT")
    except Exception as e:
        log.warning("stats_fetch_failed", proxy=proxy, error=str(e))
        return None

    trades_30d = [t for t in trades_all if int(t.get("timestamp", 0)) >= since_30d]
    trades_7d = [t for t in trades_all if int(t.get("timestamp", 0)) >= since_7d]

    if len(trades_30d) < 5:
        return None

    trade_freq = len(trades_30d) / 30.0

    # Win rate from closed positions
    closed = [p for p in positions if not p.get("redeemable") and p.get("currentValue") is not None]
    winners = [p for p in closed if float(p.get("cashPnl", 0)) > 0]
    win_rate = len(winners) / len(closed) if closed else 0.0

    # Realized PnL
    pnl_data = await get_wallet_pnl(proxy, since_30d)
    realized_pnl_30d = sum(float(p.get("realizedPnl", 0)) for p in pnl_data)
    pnl_7d_data = [p for p in pnl_data if int(p.get("lastUpdated", 0)) >= since_7d]
    recent_7d_pnl = sum(float(p.get("realizedPnl", 0)) for p in pnl_7d_data)

    # Per-trade PnL stats
    per_trade_pnls = [float(p.get("realizedPnl", 0)) for p in pnl_data if p.get("realizedPnl")]
    if len(per_trade_pnls) < 2:
        per_trade_pnl = 0.0
        per_trade_pnl_std = 1.0
    else:
        per_trade_pnl = statistics.mean(per_trade_pnls)
        per_trade_pnl_std = statistics.stdev(per_trade_pnls) or 1.0

    sharpe_like = max(-3.0, min(3.0, per_trade_pnl / per_trade_pnl_std))

    # Average position size
    initial_values = [float(p.get("initialValue", 0)) for p in positions if p.get("initialValue")]
    avg_position_usd = statistics.mean(initial_values) if initial_values else 0.0

    # Market diversity
    unique_markets = {t.get("conditionId", t.get("market", "")) for t in trades_30d}
    market_diversity = min(1.0, len(unique_markets) / max(len(trades_30d), 1))

    # Median hold hours from closed positions
    hold_hours = []
    for p in closed:
        if p.get("startDate") and p.get("endDate"):
            try:
                open_ts = datetime.fromisoformat(p["startDate"].replace("Z", "+00:00")).timestamp()
                close_ts = datetime.fromisoformat(p["endDate"].replace("Z", "+00:00")).timestamp()
                hold_hours.append((close_ts - open_ts) / 3600)
            except Exception:
                pass
    median_hold_hours = statistics.median(hold_hours) if hold_hours else 72.0

    # Last trade timestamp
    last_trade_ts = max(
        (int(t.get("timestamp", 0)) for t in trades_all), default=0
    )

    return LeaderCandidate(
        proxy_address=proxy,
        trades_30d=len(trades_30d),
        trade_freq=trade_freq,
        win_rate=win_rate,
        realized_pnl_30d=realized_pnl_30d,
        avg_position_usd=avg_position_usd,
        per_trade_pnl=per_trade_pnl,
        per_trade_pnl_std=per_trade_pnl_std,
        sharpe_like=sharpe_like,
        market_diversity=market_diversity,
        recent_7d_pnl=recent_7d_pnl,
        median_hold_hours=median_hold_hours,
        wash_score=0.0,     # filled by antigaming step
        last_trade_ts=last_trade_ts,
    )


def percentile_rank(value: float, values: list[float]) -> float:
    """What fraction of `values` is <= `value` (0.0–1.0)."""
    if not values or len(values) < 2:
        return 0.5
    below = sum(1 for v in values if v <= value)
    return below / len(values)


def compute_scores(candidates: list[LeaderCandidate]) -> list[tuple[LeaderCandidate, float]]:
    """
    Percentile-normalize each metric within the pool, then apply the weighted formula.
    Returns list of (candidate, score) sorted best-first.
    """
    if not candidates:
        return []

    # Extract metric arrays for percentile normalization
    trade_freqs = [c.trade_freq for c in candidates]
    sharpes = [c.sharpe_like for c in candidates]
    win_rates = [c.win_rate for c in candidates]
    pnl_7ds = [c.recent_7d_pnl for c in candidates]
    hold_hours = [c.median_hold_hours for c in candidates]
    diversities = [c.market_diversity for c in candidates]
    pnls_30d = [c.realized_pnl_30d for c in candidates]

    # Cold-wallet multiplier: penalize 0.5× if last_trade > 48h ago
    now = time.time()

    scored: list[tuple[LeaderCandidate, float]] = []
    for c in candidates:
        pct_freq = percentile_rank(c.trade_freq, trade_freqs)
        pct_sharpe = percentile_rank(c.sharpe_like, sharpes)
        pct_win = percentile_rank(c.win_rate, win_rates)
        pct_7d = percentile_rank(c.recent_7d_pnl, pnl_7ds)
        pct_hold_inv = 1.0 - percentile_rank(c.median_hold_hours, hold_hours)  # SHORT = high score
        pct_diversity = percentile_rank(c.market_diversity, diversities)
        pct_pnl = percentile_rank(c.realized_pnl_30d, pnls_30d)

        score = (
            0.25 * pct_freq
            + 0.20 * pct_sharpe
            + 0.15 * pct_win
            + 0.15 * pct_7d
            + 0.10 * pct_hold_inv
            + 0.10 * pct_diversity
            + 0.05 * pct_pnl
        )

        # Cold-wallet penalty
        hours_since_trade = (now - c.last_trade_ts) / 3600
        if hours_since_trade > 48:
            score *= 0.5

        scored.append((c, score))

    scored.sort(key=lambda x: (-x[1], -x[0].trades_30d, -x[0].last_trade_ts))
    return scored
