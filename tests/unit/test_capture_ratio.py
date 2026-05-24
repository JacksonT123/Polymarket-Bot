"""Unit tests for capture ratio calculation."""
import pytest
from src.metrics.capture_ratio import compute_capture_ratio


def _copies(pnl, cost) -> list[dict]:
    return [{"realized_pnl_usd": pnl, "unrealized_pnl_usd": 0.0, "cost_usd": cost}]


def _trades(pnl, cost) -> list[dict]:
    return [{"realized_pnl_usd": pnl, "unrealized_pnl_usd": 0.0, "cost_usd": cost}]


class TestCaptureRatio:
    def test_perfect_capture(self):
        ratio = compute_capture_ratio(_copies(10.0, 100.0), _trades(10.0, 100.0))
        assert ratio == pytest.approx(1.0)

    def test_half_capture(self):
        ratio = compute_capture_ratio(_copies(5.0, 100.0), _trades(10.0, 100.0))
        assert ratio == pytest.approx(0.5)

    def test_zero_lead_invested_returns_none(self):
        ratio = compute_capture_ratio(_copies(5.0, 100.0), _trades(5.0, 0.0))
        assert ratio is None

    def test_zero_bot_invested_returns_none(self):
        ratio = compute_capture_ratio(_copies(5.0, 0.0), _trades(5.0, 100.0))
        assert ratio is None

    def test_zero_lead_roi_returns_none(self):
        ratio = compute_capture_ratio(_copies(5.0, 100.0), _trades(0.0, 100.0))
        assert ratio is None

    def test_bot_over_captures(self):
        ratio = compute_capture_ratio(_copies(15.0, 100.0), _trades(10.0, 100.0))
        assert ratio == pytest.approx(1.5)

    def test_negative_capture(self):
        ratio = compute_capture_ratio(_copies(-5.0, 100.0), _trades(-10.0, 100.0))
        assert ratio == pytest.approx(0.5)

    def test_empty_lists_returns_none(self):
        assert compute_capture_ratio([], []) is None
