"""Unit tests for execution filters."""
import pytest
from datetime import datetime, timezone, timedelta
from src.core.models import SignalEvent, MarketMetadata, TradeParams
from src.core.enums import SignalDirection
from src.execution.filters import (
    filter_capital, filter_lead_size, filter_liquidity,
    filter_price_range, filter_resolution_window, run_all_filters,
)


def _signal(price=0.5, value_usd=50.0, end_hours=48.0) -> SignalEvent:
    end_date = datetime.now(timezone.utc) + timedelta(hours=end_hours) if end_hours else None
    return SignalEvent(
        wallet_address="0xabc",
        market_id="mkt-1",
        token_id="tok-1",
        side="YES",
        direction=SignalDirection.BUY,
        price=price,
        value_usd=value_usd,
        lead_timestamp=datetime.now(timezone.utc),
        detected_at=datetime.now(timezone.utc),
    )


def _market(volume=100_000.0, end_hours=48.0) -> MarketMetadata:
    return MarketMetadata(
        condition_id="mkt-1",
        question="Test market",
        volume_24h_usd=volume,
        end_date=datetime.now(timezone.utc) + timedelta(hours=end_hours) if end_hours else None,
    )


def _params(tier=0, trade_size=5.0, max_positions=10, max_deployed_pct=0.5) -> TradeParams:
    return TradeParams(tier=tier, trade_size_usd=trade_size, max_positions=max_positions, max_deployed_pct=max_deployed_pct)


class TestFilterCapital:
    def test_passes_when_sufficient(self):
        r = filter_capital(cash=100.0, trade_size=5.0, open_positions=0, max_positions=10)
        assert r.passed

    def test_blocked_on_no_cash(self):
        r = filter_capital(cash=3.0, trade_size=5.0, open_positions=0, max_positions=10)
        assert not r.passed

    def test_blocked_on_max_positions(self):
        r = filter_capital(cash=100.0, trade_size=5.0, open_positions=10, max_positions=10)
        assert not r.passed


class TestFilterLeadSize:
    def test_passes_above_minimum(self):
        r = filter_lead_size(_signal(value_usd=50.0), tier=0, wallet_win_streak=0)
        assert r.passed

    def test_blocked_below_minimum(self):
        r = filter_lead_size(_signal(value_usd=2.0), tier=0, wallet_win_streak=0)
        assert not r.passed


class TestFilterPriceRange:
    def test_passes_mid_price(self):
        r = filter_price_range(_signal(price=0.5))
        assert r.passed

    def test_blocked_too_low(self):
        r = filter_price_range(_signal(price=0.03))
        assert not r.passed

    def test_blocked_too_high(self):
        r = filter_price_range(_signal(price=0.97))
        assert not r.passed


class TestFilterResolutionWindow:
    def test_passes_within_window(self):
        r = filter_resolution_window(_market(end_hours=48.0))
        assert r.passed

    def test_blocked_already_closed(self):
        m = MarketMetadata(condition_id="x", question="q", is_closed=True)
        r = filter_resolution_window(m)
        assert not r.passed


class TestRunAllFilters:
    def test_all_pass(self):
        passed, reason, _ = run_all_filters(
            _signal(), _market(), cash_balance=100.0,
            trade_params=_params(), open_positions=0,
        )
        assert passed
        assert reason is None

    def test_fails_on_first_blocking_filter(self):
        passed, reason, results = run_all_filters(
            _signal(), _market(), cash_balance=3.0,
            trade_params=_params(trade_size=5.0), open_positions=0,
        )
        assert not passed
        assert reason is not None
