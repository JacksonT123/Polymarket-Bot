"""Shared pytest fixtures."""
from __future__ import annotations

import asyncio
import os
import tempfile

import pytest
import pytest_asyncio

# Use in-memory SQLite for all tests
os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("BOT_MODE", "PAPER")
os.environ.setdefault("ALCHEMY_API_KEY_SERVICE", "test")
os.environ.setdefault("PROXY_WALLET", "0x" + "a" * 40)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db():
    from bot.ledger.db import init_db, get_db
    await init_db()
    async with get_db() as conn:
        yield conn


def make_candidate(**kwargs):
    from bot.models import LeaderCandidate
    defaults = dict(
        proxy_address="0x" + "b" * 40,
        trades_30d=50,
        trade_freq=1.67,
        win_rate=0.60,
        realized_pnl_30d=500.0,
        avg_position_usd=50.0,
        per_trade_pnl=10.0,
        per_trade_pnl_std=15.0,
        sharpe_like=0.67,
        market_diversity=0.3,
        recent_7d_pnl=100.0,
        median_hold_hours=24.0,
        wash_score=0.0,
        last_trade_ts=int(asyncio.get_event_loop().time()),
    )
    defaults.update(kwargs)
    return LeaderCandidate(**defaults)
