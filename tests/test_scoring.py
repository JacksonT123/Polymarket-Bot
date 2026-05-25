"""Unit tests for scoring.py — percentile_rank and compute_scores."""
from __future__ import annotations

import time

import pytest

from bot.discovery.scoring import compute_scores, percentile_rank
from bot.models import LeaderCandidate


def _make(proxy: str, **kwargs) -> LeaderCandidate:
    defaults = dict(
        proxy_address=proxy,
        trades_30d=50,
        trade_freq=2.0,
        win_rate=0.6,
        realized_pnl_30d=500.0,
        avg_position_usd=50.0,
        per_trade_pnl=10.0,
        per_trade_pnl_std=15.0,
        sharpe_like=0.67,
        market_diversity=0.3,
        recent_7d_pnl=100.0,
        median_hold_hours=24.0,
        wash_score=0.0,
        last_trade_ts=int(time.time()),
    )
    defaults.update(kwargs)
    return LeaderCandidate(**defaults)


def test_percentile_rank_middle():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    rank = percentile_rank(3.0, values)
    assert 0.4 <= rank <= 0.7


def test_percentile_rank_min():
    values = [1.0, 2.0, 3.0]
    assert percentile_rank(1.0, values) < 0.5


def test_percentile_rank_max():
    values = [1.0, 2.0, 3.0]
    assert percentile_rank(3.0, values) > 0.5


def test_percentile_rank_single_value():
    assert percentile_rank(5.0, [5.0]) == 0.5


def test_compute_scores_returns_sorted():
    candidates = [
        _make("0x01", trade_freq=0.5, win_rate=0.3, realized_pnl_30d=100),
        _make("0x02", trade_freq=5.0, win_rate=0.8, realized_pnl_30d=2000),
        _make("0x03", trade_freq=2.0, win_rate=0.6, realized_pnl_30d=500),
    ]
    scored = compute_scores(candidates)
    assert len(scored) == 3
    # Best scorer should be first
    scores = [s for _, s in scored]
    assert scores == sorted(scores, reverse=True)


def test_compute_scores_cold_wallet_penalty():
    now = time.time()
    hot = _make("0xhot", last_trade_ts=int(now - 3600))      # 1h ago
    cold = _make("0xcold", last_trade_ts=int(now - 86400 * 3))  # 3 days ago

    # Make them identical except for last_trade_ts
    hot.trade_freq = cold.trade_freq = 2.0
    hot.win_rate = cold.win_rate = 0.6

    scored = compute_scores([hot, cold])
    score_map = {c.proxy_address: s for c, s in scored}

    assert score_map["0xhot"] > score_map["0xcold"]


def test_compute_scores_empty():
    assert compute_scores([]) == []


def test_score_sum_between_0_and_1():
    candidates = [_make(f"0x{i:02x}") for i in range(10)]
    scored = compute_scores(candidates)
    for _, s in scored:
        assert 0.0 <= s <= 1.0
