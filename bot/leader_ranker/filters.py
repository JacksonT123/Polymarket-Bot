from __future__ import annotations

from bot.models import LeaderCandidate

MIN_TRADES_30D = 15
MIN_DISTINCT_MARKETS = 3
MIN_VALUE_USD = 500.0
MAX_WASH_SCORE = 0.85


def apply_hard_filters(c: LeaderCandidate) -> str | None:
    if c.trade_count_30d < MIN_TRADES_30D:
        return f"trade_count_30d<{MIN_TRADES_30D}"
    if c.distinct_markets < MIN_DISTINCT_MARKETS:
        return f"distinct_markets<{MIN_DISTINCT_MARKETS}"
    if c.value_usd < MIN_VALUE_USD and c.pnl_30d <= 0:
        return f"value_usd<{MIN_VALUE_USD}"
    if c.wash_score >= MAX_WASH_SCORE:
        return "wash_score_too_high"
    if c.trade_freq_per_day > 80:
        return "trade_freq_suspicious"
    return None
