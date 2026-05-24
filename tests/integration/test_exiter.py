"""Integration tests for position exit handler."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.positions.exiter import ExitHandler, check_thesis_broken, check_time_stop
from src.core.enums import ExitReason
from src.core.clock import set_clock, reset_clock
from datetime import datetime, timezone, timedelta


def _mock_position(entry_price=0.6, size=10.0, days_open=0):
    pos = MagicMock()
    pos.id = 1
    pos.token_id = "tok-1"
    pos.entry_price = entry_price
    pos.size_shares = size
    pos.opened_at = datetime.now(timezone.utc) - timedelta(days=days_open)
    pos.status = "open"
    return pos


class TestCheckThesisBroken:
    def test_not_broken_when_price_held(self):
        pos = _mock_position(entry_price=0.6)
        assert not check_thesis_broken(pos, current_price=0.55, lead_last_trade_at=None)

    def test_broken_when_price_up_and_lead_silent(self):
        pos = _mock_position(entry_price=0.6)
        long_ago = datetime.now(timezone.utc) - timedelta(hours=100)
        result = check_thesis_broken(pos, current_price=0.65, lead_last_trade_at=long_ago)
        assert result

    def test_not_broken_when_lead_traded_recently(self):
        pos = _mock_position(entry_price=0.6)
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        result = check_thesis_broken(pos, current_price=0.65, lead_last_trade_at=recent)
        assert not result


class TestCheckTimeStop:
    def test_not_stopped_when_fresh(self):
        pos = _mock_position(days_open=1)
        assert not check_time_stop(pos)

    def test_stopped_when_old(self):
        pos = _mock_position(days_open=100)
        assert check_time_stop(pos)

    def test_no_opened_at_is_safe(self):
        pos = _mock_position()
        pos.opened_at = None
        assert not check_time_stop(pos)


class TestExitHandler:
    @pytest.mark.asyncio
    async def test_on_resolve_win(self):
        engine = MagicMock()
        session_factory = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = ctx
        ctx.commit = AsyncMock()
        ctx.add = MagicMock()

        handler = ExitHandler(engine, session_factory)
        pos = _mock_position(entry_price=0.6, size=10.0)
        await handler.on_resolve(pos, resolved_price=1.0)
        ctx.add.assert_called_once()
        ctx.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_lead_full_sell(self):
        engine = AsyncMock()
        from src.core.models import FillResult
        engine.place_sell = AsyncMock(return_value=FillResult(
            success=True, fill_price=0.7, fill_size_shares=10.0,
            cost_usd=7.0, slippage_pct=0.0, fee_usd=0.0, phase_used="paper_sell"
        ))
        session_factory = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.execute = AsyncMock(return_value=MagicMock(scalar_one=lambda: _mock_position()))
        ctx.add = MagicMock()
        ctx.commit = AsyncMock()
        session_factory.return_value = ctx

        handler = ExitHandler(engine, session_factory)
        pos = _mock_position(entry_price=0.6, size=10.0)
        await handler.on_lead_sell(pos, lead_sell_pct=1.0)
        engine.place_sell.assert_called_once()
