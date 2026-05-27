from __future__ import annotations

from bot.config import get_settings
from bot.copy_planner.bankroll import get_leader_bankroll, get_my_bankroll
from bot.copy_planner.portfolio_sizer import compute_copy_notional
from bot.data.client import DataAPIClient
from bot.models import CopyIntent, DecisionCode, LeaderTradeEvent, Side


async def build_intent(client: DataAPIClient, event: LeaderTradeEvent) -> tuple[CopyIntent | None, DecisionCode | None, dict]:
    if event.price <= 0:
        return None, DecisionCode.SKIP_PARSE_ERROR, {"reason": "bad_price"}

    leader_b = await get_leader_bankroll(client, event.leader_proxy)
    cfg = get_settings()
    if leader_b.bankroll_usd <= 0:
        return None, DecisionCode.SKIP_LEADER_BANKROLL_UNKNOWN, {"leader_bankroll": 0}
    if leader_b.stale:
        return None, DecisionCode.SKIP_LEADER_BANKROLL_STALE, {"leader_bankroll": leader_b.bankroll_usd}

    my_bankroll = await get_my_bankroll()
    target, leader_fraction, sizing = compute_copy_notional(event, leader_b.bankroll_usd, my_bankroll)
    if target < cfg.min_copy_for_mode:
        return None, DecisionCode.SKIP_MIN_SIZE, sizing

    shares = target / event.price
    if event.side == Side.SELL:
        from bot.ledger import repo

        held = await repo.get_position_shares(event.condition_id, event.token_id)
        if held <= 0:
            return None, DecisionCode.SKIP_MIN_SIZE, {**sizing, "reason": "no_position_to_sell"}
        leader_sell_fraction = min(1.0, event.usdc_size / max(leader_b.bankroll_usd * leader_fraction, 1e-9))
        shares = min(held, held * leader_sell_fraction)
        target = shares * event.price

    intent = CopyIntent(
        event_id=event.event_id,
        leader_proxy=event.leader_proxy,
        condition_id=event.condition_id,
        token_id=event.token_id,
        side=event.side,
        target_notional=target,
        target_shares=shares,
        limit_price=event.price,
        leader_fraction=leader_fraction,
        sizing_details=sizing,
    )
    return intent, None, sizing
