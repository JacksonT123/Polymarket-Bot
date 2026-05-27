from __future__ import annotations

from bot.config import get_settings
from bot.models import LeaderTradeEvent


def compute_copy_notional(
    event: LeaderTradeEvent,
    leader_bankroll: float,
    my_bankroll: float,
) -> tuple[float, float, dict]:
    cfg = get_settings()
    details: dict = {
        "leader_trade_usdc": event.usdc_size,
        "leader_bankroll": leader_bankroll,
        "my_bankroll": my_bankroll,
    }
    if leader_bankroll <= 0 or my_bankroll <= 0:
        return 0.0, 0.0, details

    leader_fraction = event.usdc_size / leader_bankroll
    leader_fraction = min(leader_fraction, cfg.max_leader_fraction_per_trade)
    details["leader_fraction"] = leader_fraction

    target = leader_fraction * my_bankroll
    target = min(target, my_bankroll * cfg.max_copy_pct_per_trade)
    target = max(target, cfg.min_copy_for_mode)
    details["target_notional"] = target
    return target, leader_fraction, details
