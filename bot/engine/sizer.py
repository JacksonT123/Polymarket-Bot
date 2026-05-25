"""
Fixed-dollar position sizing with rank multiplier.
$5 base × tier multiplier / leader_price = shares to buy.
Tier: rank 1-10 → 1.5×, rank 11-20 → 1.0×, rank 21-30 → 0.7×
"""
from __future__ import annotations

from bot.config import get_settings
from bot.models import LeaderTier, OrderSide, SignalEvent
from bot.observability.log import get_logger

log = get_logger(__name__)

_TIER_MULTIPLIERS = {
    "TOP": 1.5,    # rank 1-10
    "MID": 1.0,    # rank 11-20
    "LOW": 0.7,    # rank 21-30
}

_MIN_SHARES = 1.0
_MAX_POSITION_FRACTION = 0.10  # never more than 10% of bankroll in one position


def _tier_for_rank(rank: int) -> str:
    if rank <= 10:
        return "TOP"
    if rank <= 20:
        return "MID"
    return "LOW"


def compute_size_shares(
    signal: SignalEvent,
    execution_price: float,
    bankroll_usd: float,
) -> float:
    """
    Returns the number of shares to buy/sell.
    Returns 0.0 if the position would be too small or too large.
    """
    cfg = get_settings()

    multiplier = _TIER_MULTIPLIERS[_tier_for_rank(signal.leader_rank)]
    dollar_amount = cfg.base_trade_usd * multiplier

    # Cap at max fraction of bankroll
    max_dollar = bankroll_usd * _MAX_POSITION_FRACTION
    dollar_amount = min(dollar_amount, max_dollar)

    if execution_price <= 0:
        log.warning("sizer_zero_price", market=signal.condition_id[:12])
        return 0.0

    shares = dollar_amount / execution_price

    if shares < _MIN_SHARES:
        log.debug(
            "sizer_below_min",
            shares=shares,
            dollar=dollar_amount,
            price=execution_price,
        )
        return 0.0

    log.debug(
        "sizer_computed",
        rank=signal.leader_rank,
        multiplier=multiplier,
        dollar=dollar_amount,
        price=execution_price,
        shares=shares,
    )
    return shares


def aggregate_signals_size(
    signals: list[SignalEvent],
    execution_price: float,
    bankroll_usd: float,
) -> float:
    """
    For a batch of signals (same market, same side), compute the combined
    size — sum of per-leader sizes, capped at bankroll fraction.
    """
    cfg = get_settings()
    total_dollar = 0.0

    for s in signals:
        multiplier = _TIER_MULTIPLIERS[_tier_for_rank(s.leader_rank)]
        total_dollar += cfg.base_trade_usd * multiplier

    # Hard cap: 10% of bankroll per market per side
    max_dollar = bankroll_usd * _MAX_POSITION_FRACTION
    total_dollar = min(total_dollar, max_dollar)

    if execution_price <= 0:
        return 0.0

    shares = total_dollar / execution_price
    return shares if shares >= _MIN_SHARES else 0.0
