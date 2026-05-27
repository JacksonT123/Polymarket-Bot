from __future__ import annotations

from bot.config import get_settings
from bot.ledger import repo
from bot.models import CopyIntent, DecisionCode, Side


async def validate_intent(intent: CopyIntent, cash_usd: float, equity_usd: float) -> DecisionCode | None:
    cfg = get_settings()

    if await repo.is_kill_switch_active():
        return DecisionCode.SKIP_KILL_SWITCH

    if intent.target_notional < cfg.min_copy_for_mode:
        return DecisionCode.SKIP_MIN_SIZE

    if intent.side == Side.BUY and intent.target_notional > cash_usd + 0.01:
        return DecisionCode.SKIP_INSUFFICIENT_CASH

    market_notional = await repo.get_position_notional(intent.condition_id)
    cap = equity_usd * cfg.max_copy_pct_per_market
    if intent.side == Side.BUY and market_notional + intent.target_notional > cap:
        return DecisionCode.SKIP_MARKET_LIMIT

    if intent.side == Side.BUY and await repo.market_is_new(intent.condition_id):
        if await repo.count_open_markets() >= cfg.max_open_markets:
            return DecisionCode.SKIP_MAX_OPEN_MARKETS

    if intent.limit_price < 0.02 or intent.limit_price > 0.98:
        return DecisionCode.SKIP_MARKET_ILLQUID

    return None
