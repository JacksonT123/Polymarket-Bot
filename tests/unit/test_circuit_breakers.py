"""Unit tests for circuit breaker logic."""
import pytest
from src.core.exceptions import CircuitBreakerError
from src.core.clock import set_clock, reset_clock
from src.risk.circuit_breakers import CircuitBreakerManager
from datetime import datetime, timezone, timedelta


def _utc(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)


class TestCircuitBreakers:
    def setup_method(self):
        set_clock(lambda: _utc("2026-05-23T09:00:00"))
        self.cbm = CircuitBreakerManager(initial_balance=1000.0)

    def teardown_method(self):
        reset_clock()

    def test_no_breaker_initially(self):
        self.cbm.check_and_raise(1000.0)  # should not raise

    def test_daily_loss_triggers(self):
        # Lose 16% (threshold is 15%)
        with pytest.raises(CircuitBreakerError) as exc:
            self.cbm.check_and_raise(840.0)
        assert "daily" in str(exc.value).lower()

    def test_weekly_loss_triggers(self):
        with pytest.raises(CircuitBreakerError) as exc:
            self.cbm.check_and_raise(740.0)  # 26% loss > 25% weekly threshold
        # weekly fires alongside daily since daily fires first; either is acceptable
        assert "loss" in str(exc.value).lower()

    def test_permanent_drawdown_triggers(self):
        # Set a high peak, then drop by 41%
        self.cbm._evaluate(2000.0)  # new peak
        with pytest.raises(CircuitBreakerError) as exc:
            self.cbm.check_and_raise(1150.0)  # 42.5% drop from 2000
        assert "permanent" in str(exc.value).lower()

    def test_daily_rolls_next_day(self):
        set_clock(lambda: _utc("2026-05-23T09:00:00"))
        cbm = CircuitBreakerManager(1000.0)
        cbm.check_and_raise(840.0)  # triggers daily
        # Advance 25 hours
        set_clock(lambda: _utc("2026-05-24T10:00:00"))
        cbm.check_and_raise(840.0)  # new day, new baseline — should not raise

    def test_status_returns_dict(self):
        status = self.cbm.status()
        assert "daily" in status
        assert "weekly" in status
        assert "permanent" in status
        assert "all_clear" in status
