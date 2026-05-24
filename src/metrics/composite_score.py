import math
from config.settings import (
    W_LOG_TRADES, W_WIN_RATE_VS_CATEGORY_FLOOR, W_LOG_PROFIT_FACTOR, W_MONTHS_ACTIVE,
    W_DOMAIN_SCORE, W_HOLD_TO_RESOLUTION_PCT, W_CONSISTENCY_SCORE, W_CONVICTION_SIGNAL,
    W_COUNTER_TRADE_SIGNAL, W_ENTROPY, W_INSIDER_PROXIMITY, W_MAX_DRAWDOWN, W_CROWDING_PENALTY,
)


def compute_composite_score(
    closed_trades_count: int,
    win_rate_vs_category_floor_score: float,
    profit_factor: float,
    months_active: float,
    domain_score: float,
    hold_to_resolution_pct: float,
    consistency_score: float,
    conviction_signal: float,
    counter_trade_signal: float,
    entropy_score: float,
    insider_proximity_score: float,
    max_drawdown_pct: float,
    crowding_score: float,
) -> float:
    """Computes composite score clamped to [0, 10]."""
    s = 0.0
    s += W_LOG_TRADES             * math.log10(max(1, closed_trades_count))
    s += W_WIN_RATE_VS_CATEGORY_FLOOR * win_rate_vs_category_floor_score
    s += W_LOG_PROFIT_FACTOR      * math.log10(max(0.1, profit_factor))
    s += W_MONTHS_ACTIVE          * min(1.0, months_active / 24)
    s += W_DOMAIN_SCORE           * domain_score
    s += W_HOLD_TO_RESOLUTION_PCT * hold_to_resolution_pct
    s += W_CONSISTENCY_SCORE      * consistency_score
    s += W_CONVICTION_SIGNAL      * conviction_signal
    s += W_COUNTER_TRADE_SIGNAL   * counter_trade_signal
    s += W_ENTROPY                * entropy_score
    s += W_INSIDER_PROXIMITY      * insider_proximity_score
    s += W_MAX_DRAWDOWN           * max_drawdown_pct
    s += W_CROWDING_PENALTY       * crowding_score
    return max(0.0, min(10.0, s * 10))
