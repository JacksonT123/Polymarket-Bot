"""Handles all 8 exit reasons from the spec."""
from datetime import datetime, timezone, timedelta
import structlog
from src.core.enums import ExitReason, PositionStatus
from src.core.clock import now
from src.positions.tracker import begin_close, finalize_close, resolve_position
from config.settings import (
    THESIS_BROKEN_THRESHOLD, THESIS_BROKEN_LEAD_QUIET_H, HARD_TIME_STOP_DAYS,
)

log = structlog.get_logger(__name__)


class ExitHandler:
    def __init__(self, order_engine, session_factory):
        self._engine = order_engine
        self._session_factory = session_factory

    async def on_lead_sell(self, position, lead_sell_pct: float) -> None:
        """Lead sold X% of their position → bot sells same proportion."""
        reason = ExitReason.MIRROR_FULL if lead_sell_pct >= 0.99 else ExitReason.MIRROR_PARTIAL
        await self._execute_exit(position, reason, sell_pct=lead_sell_pct)

    async def on_resolve(self, position, resolved_price: float) -> None:
        """Market resolved — position auto-closes at $1.00 (win) or $0.00 (loss)."""
        reason = ExitReason.RESOLVE_WIN if resolved_price > 0.5 else ExitReason.RESOLVE_LOSS
        realized_pnl = (resolved_price - position.entry_price) * position.size_shares
        async with self._session_factory() as session:
            log_entry = resolve_position(position, resolved_price, realized_pnl)
            session.add(log_entry)
            await session.commit()
        log.info("position_resolved", id=position.id, reason=reason.value, pnl=realized_pnl)

    async def on_thesis_broken(self, position) -> None:
        await self._execute_exit(position, ExitReason.THESIS_BROKEN)

    async def on_time_stop(self, position) -> None:
        await self._execute_exit(position, ExitReason.TIME_STOP)

    async def on_circuit_breaker(self, position) -> None:
        await self._execute_exit(position, ExitReason.CIRCUIT_BREAKER)

    async def on_manual(self, position) -> None:
        await self._execute_exit(position, ExitReason.MANUAL)

    async def _execute_exit(self, position, reason: ExitReason, sell_pct: float = 1.0) -> None:
        shares_to_sell = position.size_shares * sell_pct
        fill = await self._engine.place_sell(position.token_id, shares_to_sell, position.entry_price)
        realized_pnl = (fill.fill_price - position.entry_price) * shares_to_sell
        async with self._session_factory() as session:
            from src.db.models import Position as PositionModel
            from sqlalchemy import select
            result = await session.execute(select(PositionModel).where(PositionModel.id == position.id))
            db_pos = result.scalar_one()
            log_begin = begin_close(db_pos, reason)
            log_final = finalize_close(db_pos, fill.fill_price, realized_pnl)
            session.add(log_begin)
            session.add(log_final)
            await session.commit()
        log.info("position_closed", id=position.id, reason=reason.value,
                 fill_price=fill.fill_price, pnl=realized_pnl)


def check_thesis_broken(position, current_price: float, lead_last_trade_at: datetime | None) -> bool:
    """Returns True if thesis-broken override should fire."""
    price_drop = (current_price - position.entry_price) / position.entry_price
    if price_drop > THESIS_BROKEN_THRESHOLD:
        return False
    lead_quiet = True
    if lead_last_trade_at:
        hours_silent = (now() - lead_last_trade_at).total_seconds() / 3600
        lead_quiet = hours_silent >= THESIS_BROKEN_LEAD_QUIET_H
    return lead_quiet


def check_time_stop(position) -> bool:
    """Returns True if position has been open >= HARD_TIME_STOP_DAYS."""
    if not position.opened_at:
        return False
    days_open = (now() - position.opened_at).days
    return days_open >= HARD_TIME_STOP_DAYS
