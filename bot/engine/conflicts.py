"""
Conflict resolution: handles YES vs NO signal collisions in the same market.
If leaders are split on direction, apply weighted vote or skip.
"""
from __future__ import annotations

from bot.models import OrderSide, SignalEvent
from bot.observability.log import get_logger

log = get_logger(__name__)


def resolve_conflicts(signals: list[SignalEvent]) -> list[SignalEvent] | None:
    """
    Given a batch of signals for the same (condition_id, outcome), check for
    conflicting BUY/SELL from different leaders.

    Rules:
    - If all same side → pass through
    - If mixed but one side has ≥ 2× the weight of the other → use majority
    - Otherwise → skip (return None, do not trade)

    Weight = tier multiplier sum per side.
    """
    if not signals:
        return None

    buy_signals = [s for s in signals if s.side == OrderSide.BUY]
    sell_signals = [s for s in signals if s.side == OrderSide.SELL]

    if not sell_signals:
        return buy_signals
    if not buy_signals:
        return sell_signals

    # Weighted vote: rank 1-10 → 1.5, 11-20 → 1.0, 21-30 → 0.7
    def weight(s: SignalEvent) -> float:
        if s.leader_rank <= 10:
            return 1.5
        if s.leader_rank <= 20:
            return 1.0
        return 0.7

    buy_weight = sum(weight(s) for s in buy_signals)
    sell_weight = sum(weight(s) for s in sell_signals)

    log.info(
        "conflict_detected",
        market=signals[0].condition_id[:12],
        buy_leaders=len(buy_signals),
        sell_leaders=len(sell_signals),
        buy_weight=round(buy_weight, 2),
        sell_weight=round(sell_weight, 2),
    )

    if buy_weight >= sell_weight * 2:
        log.info("conflict_resolved_buy", market=signals[0].condition_id[:12])
        return buy_signals
    if sell_weight >= buy_weight * 2:
        log.info("conflict_resolved_sell", market=signals[0].condition_id[:12])
        return sell_signals

    log.info("conflict_skipped", market=signals[0].condition_id[:12])
    return None
