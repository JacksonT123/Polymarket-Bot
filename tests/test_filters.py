"""Unit tests for discovery/filters.py hard filter logic."""
from __future__ import annotations

import time

import pytest

from bot.discovery.filters import hard_filter


class MockClient:
    def __init__(self, trades: list[dict], value: float = 5000.0):
        self._trades = trades
        self._value = value

    async def get_trades(self, user: str, limit: int = 500) -> list[dict]:
        return self._trades

    async def get_value(self, user: str) -> float:
        return self._value

    async def get_positions(self, **kwargs) -> list[dict]:
        return []

    async def get_activity(self, **kwargs) -> list[dict]:
        return []


def _make_trades(count: int, age_days: int = 30, side: str = "BUY") -> list[dict]:
    now = int(time.time())
    trades = []
    for i in range(count):
        ts = now - (age_days * 86400) + (i * 100)
        trades.append({"timestamp": str(ts), "side": side, "price": "0.5", "size": "10"})
    return trades


@pytest.mark.asyncio
async def test_passes_valid_wallet():
    trades = _make_trades(50, age_days=60, side="BUY")
    trades += _make_trades(10, age_days=5, side="SELL")
    client = MockClient(trades=trades, value=10000.0)
    reason = await hard_filter("0x" + "a" * 40, client)
    assert reason is None


@pytest.mark.asyncio
async def test_fails_too_few_trades():
    trades = _make_trades(10, age_days=60)
    client = MockClient(trades=trades, value=5000.0)
    reason = await hard_filter("0x" + "a" * 40, client)
    assert reason is not None
    assert "too_few" in reason


@pytest.mark.asyncio
async def test_fails_account_too_new():
    # All trades in last 5 days
    trades = _make_trades(50, age_days=5)
    client = MockClient(trades=trades, value=5000.0)
    reason = await hard_filter("0x" + "a" * 40, client)
    assert reason is not None
    assert "too_new" in reason


@pytest.mark.asyncio
async def test_fails_value_too_low():
    trades = _make_trades(50, age_days=60)
    client = MockClient(trades=trades, value=100.0)
    reason = await hard_filter("0x" + "a" * 40, client)
    assert reason is not None
    assert "too_low" in reason


@pytest.mark.asyncio
async def test_fails_value_too_high():
    trades = _make_trades(50, age_days=60)
    client = MockClient(trades=trades, value=300_000.0)
    reason = await hard_filter("0x" + "a" * 40, client)
    assert reason is not None
    assert "too_high" in reason
