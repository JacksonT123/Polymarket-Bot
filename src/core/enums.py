from enum import Enum


class WalletStatus(str, Enum):
    CANDIDATE = "candidate"
    DISQUALIFIED = "disqualified"
    SHADOW = "shadow"
    ACTIVE = "active"
    BENCH = "bench"
    SUSPENDED = "suspended"
    DROPPED = "dropped"


class TradingMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class ExitReason(str, Enum):
    MIRROR_FULL = "mirror_full"
    MIRROR_PARTIAL = "mirror_partial"
    RESOLVE_WIN = "resolve_win"
    RESOLVE_LOSS = "resolve_loss"
    RESOLVE_INVALID = "resolve_invalid"
    THESIS_BROKEN = "thesis_broken"
    TIME_STOP = "time_stop"
    CIRCUIT_BREAKER = "circuit_breaker"
    MANUAL = "manual"


class PositionStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    RESOLVED = "resolved"


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class SignalOutcome(str, Enum):
    EXECUTED = "executed"
    SKIPPED_CAPITAL = "skipped:capital"
    SKIPPED_LEAD_SIZE = "skipped:lead_size"
    SKIPPED_LIQUIDITY = "skipped:liquidity"
    SKIPPED_PRICE_RANGE = "skipped:price_range"
    SKIPPED_RESOLUTION_WINDOW = "skipped:resolution_window"
    SKIPPED_DUPLICATE = "skipped:duplicate"
    SKIPPED_CIRCUIT_BREAKER = "skipped:circuit_breaker"
    SKIPPED_KILLSWITCH = "skipped:killswitch"
    ERRORED = "errored"
    UNFILLABLE = "unfillable"


class NotificationSeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"
    URGENT = "URGENT"


class TierTransitionReason(str, Enum):
    PROMOTION = "promotion"
    DEMOTION = "demotion"
    MANUAL_OVERRIDE = "manual_override"


class CircuitBreakerType(str, Enum):
    DAILY_LOSS = "daily_loss"
    WEEKLY_LOSS = "weekly_loss"
    PERMANENT_DRAWDOWN = "permanent_drawdown"
