"""Integration test for paper order engine."""
import pytest
from datetime import datetime, timezone
from src.core.models import SignalEvent, TradeParams, FillResult
from src.core.enums import SignalDirection
from src.execution.order_engine import OrderEngine


def _signal() -> SignalEvent:
    return SignalEvent(
        wallet_address="0xabc",
        market_id="mkt-test",
        token_id="tok-test",
        side="YES",
        direction=SignalDirection.BUY,
        price=0.55,
        value_usd=100.0,
        lead_timestamp=datetime.now(timezone.utc),
        detected_at=datetime.now(timezone.utc),
    )


def _params() -> TradeParams:
    return TradeParams(tier=0, trade_size_usd=5.0, max_positions=10, max_deployed_pct=0.5)


class TestPaperOrderEngine:
    @pytest.mark.asyncio
    async def test_paper_buy_returns_fill(self):
        engine = OrderEngine(is_live=False)
        fill = await engine.place_buy(_signal(), _params(), market_volume_24h_usd=50_000.0)
        assert isinstance(fill, FillResult)
        assert fill.success
        assert fill.fill_price > 0
        assert fill.fill_size_shares > 0
        assert fill.cost_usd > 0

    @pytest.mark.asyncio
    async def test_paper_sell_returns_fill(self):
        engine = OrderEngine(is_live=False)
        fill = await engine.place_sell("tok-test", 10.0, entry_price=0.55)
        assert fill.success
        assert fill.fill_price == 0.55

    @pytest.mark.asyncio
    async def test_fill_price_within_slippage_bounds(self):
        engine = OrderEngine(is_live=False)
        signal = _signal()
        fill = await engine.place_buy(signal, _params(), market_volume_24h_usd=50_000.0)
        # Fill price should be slightly above entry price due to slippage
        assert fill.fill_price >= signal.price * 0.99
        assert fill.fill_price <= signal.price * 1.05
