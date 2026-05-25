"""Unit tests for antigaming wash-trading detection."""
from __future__ import annotations

import time

import pytest

from bot.discovery.antigaming import (
    _extreme_price_score,
    _repetition_score,
    _round_trip_score,
    _volume_pnl_imbalance_score,
)


def _trade(side: str, price: float = 0.5, market: str = "MKT1", ts: int = 0) -> dict:
    return {"side": side, "price": str(price), "conditionId": market, "timestamp": str(ts), "size": "10"}


def test_round_trip_score_flags_fast_flip():
    now = int(time.time())
    trades = [
        _trade("BUY", market="A", ts=now),
        _trade("SELL", market="A", ts=now + 300),  # 5 min later
    ] * 10  # 20 trades, 10 are round trips = 50%
    score = _round_trip_score(trades)
    assert score == 0.3


def test_round_trip_score_clean():
    now = int(time.time())
    trades = [
        _trade("BUY", market="A", ts=now),
        _trade("SELL", market="A", ts=now + 7200),  # 2 hours later
    ] * 5
    score = _round_trip_score(trades)
    assert score == 0.0


def test_extreme_price_score_flags():
    trades = [
        _trade("BUY", price=0.005),  # extreme
        _trade("BUY", price=0.995),  # extreme
        _trade("SELL", price=0.5),
        _trade("BUY", price=0.5),
        _trade("BUY", price=0.5),
    ]
    # 2/5 = 40% > 20% threshold
    score = _extreme_price_score(trades)
    assert score == 0.4


def test_extreme_price_score_clean():
    trades = [_trade("BUY", price=0.5) for _ in range(10)]
    assert _extreme_price_score(trades) == 0.0


def test_repetition_score_hhi_flag():
    # All trades in same market same day → HHI = 1.0 > 0.4
    now = int(time.time())
    day_start = (now // 86400) * 86400
    trades = [
        {"conditionId": "MKT1", "timestamp": str(day_start + i * 60), "side": "BUY", "price": "0.5", "size": "10"}
        for i in range(10)
    ]
    score = _repetition_score(trades)
    assert score == 0.5


def test_repetition_score_diverse():
    now = int(time.time())
    day_start = (now // 86400) * 86400
    trades = [
        {"conditionId": f"MKT{i}", "timestamp": str(day_start + i * 60), "side": "BUY", "price": "0.5", "size": "10"}
        for i in range(10)
    ]
    score = _repetition_score(trades)
    assert score == 0.0


def test_volume_pnl_imbalance_low_volume():
    trades = [_trade("BUY", price=0.5) for _ in range(5)]
    # Volume < $50k → score = 0
    assert _volume_pnl_imbalance_score(trades) == 0.0


def test_empty_trades():
    assert _round_trip_score([]) == 0.0
    assert _extreme_price_score([]) == 0.0
    assert _repetition_score([]) == 0.0
    assert _volume_pnl_imbalance_score([]) == 0.0
