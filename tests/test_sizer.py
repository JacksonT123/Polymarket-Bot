"""Unit tests for engine/sizer.py."""
from __future__ import annotations

import time

import pytest

from bot.engine.sizer import aggregate_signals_size, compute_size_shares
from bot.models import OrderSide, SignalEvent, SignalStatus


def _signal(rank: int = 5, price: float = 0.5) -> SignalEvent:
    return SignalEvent(
        proxy_address="0x" + "a" * 40,
        leader_rank=rank,
        condition_id="0x" + "b" * 64,
        token_id="123",
        outcome="YES",
        side=OrderSide.BUY,
        leader_price=price,
        leader_size=100.0,
        detected_ts=int(time.time()),
        status=SignalStatus.PENDING,
    )


def test_top_rank_multiplier():
    s = _signal(rank=5)
    # base=$5, multiplier=1.5×, price=0.5 → $7.50 / 0.5 = 15 shares
    shares = compute_size_shares(s, execution_price=0.5, bankroll_usd=500.0)
    assert abs(shares - 15.0) < 0.01


def test_mid_rank_multiplier():
    s = _signal(rank=15)
    # base=$5, multiplier=1.0×, price=0.5 → $5 / 0.5 = 10 shares
    shares = compute_size_shares(s, execution_price=0.5, bankroll_usd=500.0)
    assert abs(shares - 10.0) < 0.01


def test_low_rank_multiplier():
    s = _signal(rank=28)
    # base=$5, multiplier=0.7×, price=0.5 → $3.50 / 0.5 = 7 shares
    shares = compute_size_shares(s, execution_price=0.5, bankroll_usd=500.0)
    assert abs(shares - 7.0) < 0.01


def test_bankroll_cap():
    s = _signal(rank=5)
    # bankroll=$100, cap=10% → $10 max; price=0.5 → 20 shares
    # but rank 5 → $7.5 which is under cap
    shares = compute_size_shares(s, execution_price=0.5, bankroll_usd=100.0)
    assert shares <= 100.0 * 0.10 / 0.5


def test_zero_price_returns_zero():
    s = _signal(rank=5)
    assert compute_size_shares(s, execution_price=0.0, bankroll_usd=500.0) == 0.0


def test_aggregate_sums_leaders():
    signals = [_signal(rank=5), _signal(rank=15)]
    # rank5 → $7.5, rank15 → $5 → $12.5 total; price=0.5 → 25 shares
    shares = aggregate_signals_size(signals, execution_price=0.5, bankroll_usd=1000.0)
    assert abs(shares - 25.0) < 0.01


def test_aggregate_respects_cap():
    signals = [_signal(rank=5) for _ in range(20)]
    # Would be 20 × $7.5 = $150, but bankroll=$500, cap=$50
    shares = aggregate_signals_size(signals, execution_price=0.5, bankroll_usd=500.0)
    assert shares <= 500.0 * 0.10 / 0.5 + 0.01
