"""
Order engine: delegates to paper_fill in PAPER mode, calls CLOB in LIVE mode.
3-phase retry: FOK exact → FOK ±2% → market with slippage cap.
"""
import asyncio
import structlog
from src.core.models import SignalEvent, TradeParams, FillResult
from src.core.exceptions import OrderUnfillableError
from config.settings import (
    MAX_BUY_SLIPPAGE_PCT, MAX_SELL_SLIPPAGE_PCT,
    ORDER_PHASE_1_TOLERANCE, ORDER_PHASE_2_TOLERANCE, ORDER_PHASE_3_TOLERANCE,
)

log = structlog.get_logger(__name__)


class OrderEngine:
    def __init__(self, is_live: bool = False):
        self.is_live = is_live

    async def place_buy(
        self,
        signal: SignalEvent,
        trade_params: TradeParams,
        market_volume_24h_usd: float,
        market_category: str = "_default",
    ) -> FillResult:
        if not self.is_live:
            from src.execution.paper_fill import simulate_fill
            return simulate_fill(signal, trade_params, market_volume_24h_usd, market_category)
        return await self._live_buy(signal, trade_params)

    async def place_sell(
        self,
        token_id: str,
        size_shares: float,
        entry_price: float,
        is_live: bool = False,
    ) -> FillResult:
        if not self.is_live:
            # Paper sell: assume fill at current market price (simplified)
            return FillResult(
                success=True,
                fill_price=entry_price,
                fill_size_shares=size_shares,
                cost_usd=0.0,
                slippage_pct=0.0,
                fee_usd=0.0,
                phase_used="paper_sell",
            )
        return await self._live_sell(token_id, size_shares)

    async def _live_buy(self, signal: SignalEvent, trade_params: TradeParams) -> FillResult:
        """3-phase retry for live order placement."""
        phases = [
            (ORDER_PHASE_1_TOLERANCE, "fok_exact"),
            (ORDER_PHASE_2_TOLERANCE, "fok_2pct"),
            (ORDER_PHASE_3_TOLERANCE, "market"),
        ]
        for tolerance, phase_name in phases:
            try:
                result = await self._submit_clob_order(
                    signal, trade_params, tolerance, phase_name
                )
                if result.success:
                    log.info("order_filled", phase=phase_name, price=result.fill_price)
                    return result
            except Exception as e:
                log.warning("order_phase_failed", phase=phase_name, error=str(e))
                await asyncio.sleep(0.5)

        raise OrderUnfillableError(f"All 3 phases failed for {signal.market_id}/{signal.side}")

    async def _submit_clob_order(
        self, signal: SignalEvent, trade_params: TradeParams,
        tolerance: float, phase_name: str
    ) -> FillResult:
        # Live CLOB integration point — wired in when TRADING_MODE=LIVE
        # Requires py-clob-client and EIP-712 signing via web3
        raise NotImplementedError("Live CLOB order placement requires POLYMARKET_PRIVATE_KEY")

    async def _live_sell(self, token_id: str, size_shares: float) -> FillResult:
        raise NotImplementedError("Live sell requires POLYMARKET_PRIVATE_KEY")
