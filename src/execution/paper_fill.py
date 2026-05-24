"""Paper mode fill simulator. Applies slippage and fees; always fills if filters passed."""
from src.core.models import SignalEvent, TradeParams, FillResult
from src.metrics.slippage_estimator import estimate_slippage


FEE_BY_CATEGORY = {
    "crypto": 0.018,
    "_default": 0.010,
}


def simulate_fill(
    signal: SignalEvent,
    trade_params: TradeParams,
    market_volume_24h_usd: float,
    market_category: str = "_default",
) -> FillResult:
    """
    Simulates a paper fill with realistic slippage and fees.
    No execution failures in paper mode — if filters passed, paper fills.
    """
    slippage_pct = estimate_slippage(market_volume_24h_usd, trade_params.trade_size_usd) or 0.025
    fee_pct = FEE_BY_CATEGORY.get(market_category, FEE_BY_CATEGORY["_default"])

    fill_price = signal.price * (1 + slippage_pct)
    fill_price = min(fill_price, 0.99)  # can't pay > $0.99 for a binary

    fee_usd = trade_params.trade_size_usd * fee_pct
    size_shares = trade_params.trade_size_usd / fill_price

    return FillResult(
        success=True,
        fill_price=round(fill_price, 6),
        fill_size_shares=round(size_shares, 4),
        cost_usd=round(trade_params.trade_size_usd + fee_usd, 4),
        slippage_pct=round(slippage_pct * 100, 3),
        fee_usd=round(fee_usd, 4),
        phase_used="paper",
    )
