"""Unit tests for composite scoring."""
import pytest
from src.metrics.composite_score import compute_composite_score


def _call(**overrides) -> float:
    defaults = dict(
        closed_trades_count=200,
        win_rate_vs_category_floor_score=0.5,
        profit_factor=1.5,
        months_active=12,
        domain_score=0.6,
        hold_to_resolution_pct=0.5,
        consistency_score=0.5,
        conviction_signal=0.5,
        counter_trade_signal=0.0,
        entropy_score=0.5,
        insider_proximity_score=0.0,
        max_drawdown_pct=0.1,
        crowding_score=0.3,
    )
    defaults.update(overrides)
    return compute_composite_score(**defaults)


class TestCompositeScore:
    def test_returns_float(self):
        assert isinstance(_call(), float)

    def test_score_clamped_0_to_10(self):
        score = _call()
        assert 0.0 <= score <= 10.0

    def test_more_trades_increases_score(self):
        low = _call(closed_trades_count=100)
        high = _call(closed_trades_count=2000)
        assert high > low

    def test_higher_win_rate_increases_score(self):
        low = _call(win_rate_vs_category_floor_score=0.0)
        high = _call(win_rate_vs_category_floor_score=1.0)
        assert high > low

    def test_counter_trade_signal_reduces_score(self):
        normal = _call(counter_trade_signal=0.0)
        penalized = _call(counter_trade_signal=1.0)
        assert penalized < normal
