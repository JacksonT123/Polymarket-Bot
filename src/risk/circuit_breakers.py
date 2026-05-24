"""Circuit breakers — daily, weekly, permanent drawdown halts."""
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import structlog
from config.settings import (
    DAILY_LOSS_HALT_PCT, WEEKLY_LOSS_HALT_PCT, PERMANENT_HALT_DRAWDOWN_PCT,
)
from src.core.enums import CircuitBreakerType
from src.core.exceptions import CircuitBreakerError
from src.core.clock import now

log = structlog.get_logger(__name__)


@dataclass
class BreakerState:
    active: bool = False
    breaker_type: str = ""
    triggered_at: datetime | None = None
    halt_until: datetime | None = None
    threshold_pct: float = 0.0
    current_pct: float = 0.0


class CircuitBreakerManager:
    def __init__(self, initial_balance: float):
        self.initial_balance = initial_balance
        self.peak_equity = initial_balance
        self._daily = BreakerState()
        self._weekly = BreakerState()
        self._permanent = BreakerState()
        self._daily_start_equity: float = initial_balance
        self._weekly_start_equity: float = initial_balance
        self._day_start: datetime = now()
        self._week_start: datetime = now()

    def check_and_raise(self, current_equity: float) -> None:
        """Call before every new order. Raises CircuitBreakerError if any breaker is active."""
        self._roll_periods(current_equity)
        self._evaluate(current_equity)

        if self._permanent.active:
            raise CircuitBreakerError(CircuitBreakerType.PERMANENT_DRAWDOWN.value)
        if self._weekly.active and self._weekly.halt_until and now() < self._weekly.halt_until:
            raise CircuitBreakerError(CircuitBreakerType.WEEKLY_LOSS.value)
        if self._daily.active and self._daily.halt_until and now() < self._daily.halt_until:
            raise CircuitBreakerError(CircuitBreakerType.DAILY_LOSS.value)

    def _evaluate(self, equity: float) -> None:
        if equity > self.peak_equity:
            self.peak_equity = equity

        # Permanent drawdown from peak
        if self.peak_equity > 0:
            drawdown = (self.peak_equity - equity) / self.peak_equity
            if drawdown >= PERMANENT_HALT_DRAWDOWN_PCT and not self._permanent.active:
                self._permanent = BreakerState(
                    active=True, breaker_type="permanent_drawdown",
                    triggered_at=now(), threshold_pct=PERMANENT_HALT_DRAWDOWN_PCT,
                    current_pct=drawdown,
                )
                log.critical("circuit_breaker_permanent", drawdown=f"{drawdown:.1%}")

        # Weekly loss
        weekly_loss = (self._weekly_start_equity - equity) / self._weekly_start_equity
        if weekly_loss >= WEEKLY_LOSS_HALT_PCT and not self._weekly.active:
            self._weekly = BreakerState(
                active=True, breaker_type="weekly_loss",
                triggered_at=now(),
                halt_until=now() + timedelta(days=7),
                threshold_pct=WEEKLY_LOSS_HALT_PCT, current_pct=weekly_loss,
            )
            log.critical("circuit_breaker_weekly", loss=f"{weekly_loss:.1%}")

        # Daily loss
        daily_loss = (self._daily_start_equity - equity) / self._daily_start_equity
        if daily_loss >= DAILY_LOSS_HALT_PCT and not self._daily.active:
            self._daily = BreakerState(
                active=True, breaker_type="daily_loss",
                triggered_at=now(),
                halt_until=now() + timedelta(hours=24),
                threshold_pct=DAILY_LOSS_HALT_PCT, current_pct=daily_loss,
            )
            log.warning("circuit_breaker_daily", loss=f"{daily_loss:.1%}")

    def _roll_periods(self, equity: float) -> None:
        n = now()
        if (n - self._day_start).days >= 1:
            self._daily_start_equity = equity
            self._daily = BreakerState()
            self._day_start = n
        if (n - self._week_start).days >= 7:
            self._weekly_start_equity = equity
            self._weekly = BreakerState()
            self._week_start = n

    def manual_reset_permanent(self) -> None:
        """Requires explicit operator action to restart after permanent halt."""
        self._permanent = BreakerState()
        self.peak_equity = 0.0
        log.warning("circuit_breaker_permanent_reset_manual")

    def status(self) -> dict:
        n = now()
        return {
            "daily": {
                "active": self._daily.active,
                "current_loss": f"{(self._daily_start_equity - 0) / self._daily_start_equity:.1%}" if self._daily_start_equity else "0%",
                "threshold": f"{DAILY_LOSS_HALT_PCT:.0%}",
                "clears_at": self._daily.halt_until.isoformat() if self._daily.halt_until else None,
            },
            "weekly": {
                "active": self._weekly.active,
                "threshold": f"{WEEKLY_LOSS_HALT_PCT:.0%}",
                "clears_at": self._weekly.halt_until.isoformat() if self._weekly.halt_until else None,
            },
            "permanent": {
                "active": self._permanent.active,
                "peak_equity": self.peak_equity,
                "threshold": f"{PERMANENT_HALT_DRAWDOWN_PCT:.0%}",
            },
            "all_clear": not any([self._daily.active, self._weekly.active, self._permanent.active]),
        }
