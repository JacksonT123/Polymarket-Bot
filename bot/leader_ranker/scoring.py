from __future__ import annotations

import statistics
import time
from datetime import datetime, timedelta, timezone

from bot.data.client import DataAPIClient
from bot.leader_ranker.filters import apply_hard_filters
from bot.models import LeaderCandidate
from bot.observability.log import get_logger

log = get_logger(__name__)


def _norm(values: list[float], x: float) -> float:
    if not values:
        return 0.0
    lo, hi = min(values), max(values)
    if hi <= lo:
        return 0.5
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def _wash_heuristic(trades_30d: list[dict]) -> float:
    if len(trades_30d) < 10:
        return 0.0
    sizes = []
    for t in trades_30d:
        try:
            sizes.append(float(t.get("usdcSize") or 0) or float(t.get("size", 0)) * float(t.get("price", 0)))
        except (TypeError, ValueError):
            continue
    if len(sizes) < 5:
        return 0.0
    mean = statistics.mean(sizes)
    if mean <= 0:
        return 0.0
    stdev = statistics.pstdev(sizes)
    tiny = sum(1 for s in sizes if s < mean * 0.05)
    return min(1.0, (tiny / len(sizes)) * 0.6 + (stdev / mean) * 0.2)


async def build_candidate(
    client: DataAPIClient, proxy: str
) -> tuple[LeaderCandidate | None, set[str]]:
    since_30d = int((datetime.now(tz=timezone.utc) - timedelta(days=30)).timestamp())
    since_7d = int((datetime.now(tz=timezone.utc) - timedelta(days=7)).timestamp())

    trades = await client.get_trades(proxy, limit=150)
    positions = await client.get_positions(proxy, limit=100)

    trades_30d = [t for t in trades if int(t.get("timestamp", 0)) >= since_30d]
    trades_7d = [t for t in trades if int(t.get("timestamp", 0)) >= since_7d]
    markets = {str(t.get("conditionId") or "") for t in trades_30d if t.get("conditionId")}
    if len(trades_30d) < 5:
        return None, markets

    value_usd = sum(float(p.get("currentValue") or 0) for p in positions)

    pnl_30d = sum(float(p.get("cashPnl") or p.get("realizedPnl") or 0) for p in positions)
    pnl_7d = pnl_30d * 0.35
    if trades_7d:
        pnl_7d = sum(
            float(t.get("usdcSize") or 0) * (1 if str(t.get("side")).upper() == "BUY" else -1) * 0.01
            for t in trades_7d[:20]
        )

    closed = [p for p in positions if p.get("currentValue") is not None]
    winners = [p for p in closed if float(p.get("cashPnl", 0) or 0) > 0]
    win_rate = len(winners) / len(closed) if closed else 0.5

    timestamps = [int(t.get("timestamp", 0)) for t in trades if t.get("timestamp")]
    account_age_days = 30
    if timestamps:
        account_age_days = max(1, (int(time.time()) - min(timestamps)) // 86400)

    candidate = LeaderCandidate(
        proxy=proxy,
        pnl_30d=pnl_30d,
        pnl_7d=pnl_7d,
        win_rate=win_rate,
        trade_count_30d=len(trades_30d),
        distinct_markets=len(markets),
        max_drawdown=0.15,
        trade_freq_per_day=len(trades_30d) / 30.0,
        account_age_days=account_age_days,
        value_usd=value_usd,
        wash_score=_wash_heuristic(trades_30d),
    )
    return candidate, markets


def score_candidates(candidates: list[LeaderCandidate]) -> list[LeaderCandidate]:
    if not candidates:
        return []
    pnl30 = [c.pnl_30d for c in candidates]
    pnl7 = [c.pnl_7d for c in candidates]
    wr = [c.win_rate for c in candidates]
    freq = [c.trade_freq_per_day for c in candidates]
    div = [float(c.distinct_markets) for c in candidates]
    wash = [c.wash_score for c in candidates]

    for c in candidates:
        risk_adj = c.pnl_30d / max(1.0 + c.max_drawdown * 100, 1.0)
        c.score = (
            0.30 * _norm(pnl30, c.pnl_30d)
            + 0.15 * _norm(pnl7, c.pnl_7d)
            + 0.10 * _norm(wr, c.win_rate)
            + 0.20 * _norm(pnl30, risk_adj)
            + 0.10 * _norm(freq, c.trade_freq_per_day)
            + 0.10 * _norm(div, float(c.distinct_markets))
            + 0.05 * (1.0 - _norm(wash, c.wash_score))
            - 0.10 * _norm(wash, c.wash_score)
        )
        reason = apply_hard_filters(c)
        c.exclude_reason = reason
    return sorted(
        [c for c in candidates if c.exclude_reason is None],
        key=lambda x: x.score,
        reverse=True,
    )
