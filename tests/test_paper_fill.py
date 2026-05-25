"""Integration test for paper fill engine."""
from __future__ import annotations

import time

import pytest
import pytest_asyncio

from bot.models import BookLevel, OrderBook, OrderIntent, OrderSide
from bot.paper.fill_engine import simulate_fill


def _book(bid: float = 0.48, ask: float = 0.52, depth: float = 1000.0) -> OrderBook:
    return OrderBook(
        token_id="tok1",
        bids=[BookLevel(price=bid, size=depth)],
        asks=[BookLevel(price=ask, size=depth)],
        timestamp=int(time.time()),
    )


def _intent(side: OrderSide = OrderSide.BUY, shares: float = 10.0, price: float = 0.52) -> OrderIntent:
    return OrderIntent(
        condition_id="0x" + "c" * 64,
        token_id="tok1",
        outcome="YES",
        side=side,
        limit_price=price,
        size_shares=shares,
        client_order_id="test_order_001",
        signal_ids=[],
        leader_ranks=[5],
    )


@pytest.mark.asyncio
async def test_paper_fill_buy_succeeds():
    import bot.paper.book_cache as bc
    # Patch book cache to return our book
    original = bc.get_book_for_fill
    bc.get_book_for_fill = lambda tid, side, price: _book()

    intent = _intent(side=OrderSide.BUY, shares=10.0, price=0.53)
    result = await simulate_fill(intent)

    bc.get_book_for_fill = original

    from bot.models import OrderStatus
    assert result.status == OrderStatus.FILLED
    assert result.filled_shares == 10.0
    assert result.avg_price > intent.limit_price  # VWAP nudge on buy


@pytest.mark.asyncio
async def test_paper_fill_rejected_insufficient_depth():
    import bot.paper.book_cache as bc
    # Shallow book: only 5 shares available
    original = bc.get_book_for_fill
    bc.get_book_for_fill = lambda tid, side, price: _book(depth=5.0)

    intent = _intent(side=OrderSide.BUY, shares=100.0, price=0.53)
    result = await simulate_fill(intent)

    bc.get_book_for_fill = original

    from bot.models import OrderStatus
    assert result.status == OrderStatus.REJECTED
    assert result.filled_shares == 0.0


@pytest.mark.asyncio
async def test_paper_fill_sell_price_lower():
    import bot.paper.book_cache as bc
    original = bc.get_book_for_fill
    bc.get_book_for_fill = lambda tid, side, price: _book()

    intent = _intent(side=OrderSide.SELL, shares=10.0, price=0.48)
    result = await simulate_fill(intent)

    bc.get_book_for_fill = original

    from bot.models import OrderStatus
    assert result.status == OrderStatus.FILLED
    assert result.avg_price < intent.limit_price  # VWAP nudge on sell


@pytest.mark.asyncio
async def test_paper_fill_fee_applied():
    import bot.paper.book_cache as bc
    original = bc.get_book_for_fill
    bc.get_book_for_fill = lambda tid, side, price: _book()

    intent = _intent(shares=10.0, price=0.53)
    result = await simulate_fill(intent)

    bc.get_book_for_fill = original

    from bot.models import OrderStatus
    assert result.fee_usd > 0
