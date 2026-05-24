"""Shared pytest fixtures."""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch


@pytest.fixture
def fixed_now():
    """Freeze time to a fixed UTC datetime for deterministic tests."""
    t = datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)
    with patch("src.core.clock._clock", lambda: t):
        yield t


@pytest.fixture
def sample_trades():
    """Minimal trade list for metric tests."""
    return [
        {"side": "BUY", "outcome": "win",  "pnl": 10.0, "value": 100.0, "category": "soccer",   "opened_at": "2026-01-01", "closed_at": "2026-01-02"},
        {"side": "BUY", "outcome": "win",  "pnl": 8.0,  "value": 80.0,  "category": "soccer",   "opened_at": "2026-01-03", "closed_at": "2026-01-04"},
        {"side": "BUY", "outcome": "loss", "pnl": -5.0, "value": 50.0,  "category": "politics", "opened_at": "2026-01-05", "closed_at": "2026-01-06"},
        {"side": "BUY", "outcome": "win",  "pnl": 12.0, "value": 120.0, "category": "soccer",   "opened_at": "2026-02-01", "closed_at": "2026-02-03"},
        {"side": "BUY", "outcome": "loss", "pnl": -4.0, "value": 40.0,  "category": "soccer",   "opened_at": "2026-02-05", "closed_at": "2026-02-06"},
    ]
