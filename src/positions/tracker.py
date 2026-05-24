"""Position state machine — all transitions from spec."""
from datetime import datetime, timezone
from src.core.enums import PositionStatus, ExitReason
from src.core.exceptions import InvalidPositionTransitionError
from src.core.clock import now
from src.db.models import Position, PositionStateLog

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PositionStatus.PENDING.value:  {PositionStatus.OPEN.value},
    PositionStatus.OPEN.value:     {PositionStatus.CLOSING.value, PositionStatus.RESOLVED.value},
    PositionStatus.CLOSING.value:  {PositionStatus.CLOSED.value},
    PositionStatus.CLOSED.value:   set(),
    PositionStatus.RESOLVED.value: set(),
}


def transition(position: Position, to_status: PositionStatus, reason: str | None = None) -> PositionStateLog:
    """Apply a status transition; raises if invalid. Returns the state log entry."""
    from_val = position.status
    to_val = to_status.value
    if to_val not in ALLOWED_TRANSITIONS.get(from_val, set()):
        raise InvalidPositionTransitionError(from_val, to_val)
    position.status = to_val
    return PositionStateLog(
        position_id=position.id,
        from_status=from_val,
        to_status=to_val,
        reason=reason,
        timestamp=now(),
    )


def open_position(position: Position) -> PositionStateLog:
    return transition(position, PositionStatus.OPEN, reason="filled")


def begin_close(position: Position, exit_reason: ExitReason) -> PositionStateLog:
    position.exit_reason = exit_reason.value
    return transition(position, PositionStatus.CLOSING, reason=exit_reason.value)


def finalize_close(position: Position, exit_price: float, realized_pnl: float) -> PositionStateLog:
    position.exit_price = exit_price
    position.realized_pnl_usd = realized_pnl
    position.closed_at = now()
    return transition(position, PositionStatus.CLOSED)


def resolve_position(position: Position, exit_price: float, realized_pnl: float) -> PositionStateLog:
    position.exit_price = exit_price
    position.realized_pnl_usd = realized_pnl
    position.closed_at = now()
    return transition(position, PositionStatus.RESOLVED)
