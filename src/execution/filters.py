"""5 execution filters. Each returns a FilterResult. All must pass to execute."""
from datetime import datetime, timezone
from src.core.models import SignalEvent, FilterResult, TradeParams
from src.core.enums import SignalOutcome
from config.settings import (
    MIN_LEAD_TRADE_USD, MIN_MARKET_VOLUME_24H_USD, MIN_PRICE, MAX_PRICE,
    MIN_HOURS_TO_RESOLUTION, MAX_HOURS_TO_RESOLUTION,
    TIER2_LOW_VOLUME_LEAD_MIN_USD, TIER3_STREAK_MIN_WINS,
)
from src.core.models import MarketMetadata


def filter_capital(
    cash_balance: float,
    trade_size_usd: float,
    open_positions: int,
    max_positions: int,
    fee_pct: float = 0.01,
) -> FilterResult:
    total_needed = trade_size_usd * (1 + fee_pct)
    if cash_balance < total_needed:
        return FilterResult(
            passed=False,
            reason=SignalOutcome.SKIPPED_CAPITAL,
            detail=f"need ${total_needed:.2f}, have ${cash_balance:.2f}",
        )
    if open_positions >= max_positions:
        return FilterResult(
            passed=False,
            reason=SignalOutcome.SKIPPED_CAPITAL,
            detail=f"position cap {open_positions}/{max_positions}",
        )
    return FilterResult(passed=True)


def filter_lead_size(
    signal: SignalEvent,
    tier: int,
    wallet_win_streak: int = 0,
) -> FilterResult:
    min_size = MIN_LEAD_TRADE_USD
    # Tier 3+ unlock: allow sub-$5 trades on a win streak
    if tier >= 3 and wallet_win_streak >= TIER3_STREAK_MIN_WINS:
        min_size = 1.0
    if signal.value_usd < min_size:
        return FilterResult(
            passed=False,
            reason=SignalOutcome.SKIPPED_LEAD_SIZE,
            detail=f"lead size ${signal.value_usd:.2f} < min ${min_size:.2f}",
        )
    return FilterResult(passed=True)


def filter_liquidity(
    market: MarketMetadata,
    signal: SignalEvent,
    tier: int,
) -> FilterResult:
    min_vol = MIN_MARKET_VOLUME_24H_USD
    # Tier 2+ unlock: lower volume floor for large lead trades
    if tier >= 2 and signal.value_usd >= TIER2_LOW_VOLUME_LEAD_MIN_USD:
        min_vol = 1_000.0
    if market.volume_24h_usd < min_vol:
        return FilterResult(
            passed=False,
            reason=SignalOutcome.SKIPPED_LIQUIDITY,
            detail=f"24h vol ${market.volume_24h_usd:,.0f} < min ${min_vol:,.0f}",
        )
    return FilterResult(passed=True)


def filter_price_range(signal: SignalEvent) -> FilterResult:
    if not (MIN_PRICE <= signal.price <= MAX_PRICE):
        return FilterResult(
            passed=False,
            reason=SignalOutcome.SKIPPED_PRICE_RANGE,
            detail=f"price {signal.price} outside [{MIN_PRICE}, {MAX_PRICE}]",
        )
    return FilterResult(passed=True)


def filter_resolution_window(market: MarketMetadata) -> FilterResult:
    if market.is_closed:
        return FilterResult(
            passed=False,
            reason=SignalOutcome.SKIPPED_RESOLUTION_WINDOW,
            detail="market is closed",
        )
    if market.end_date is None:
        return FilterResult(passed=True)  # no end date = open-ended market, allow it
    now = datetime.now(timezone.utc)
    hours_remaining = (market.end_date - now).total_seconds() / 3600
    if hours_remaining < MIN_HOURS_TO_RESOLUTION:
        return FilterResult(
            passed=False,
            reason=SignalOutcome.SKIPPED_RESOLUTION_WINDOW,
            detail=f"resolves too soon ({hours_remaining:.1f}h < {MIN_HOURS_TO_RESOLUTION}h)",
        )
    if hours_remaining > MAX_HOURS_TO_RESOLUTION:
        return FilterResult(
            passed=False,
            reason=SignalOutcome.SKIPPED_RESOLUTION_WINDOW,
            detail=f"resolves too far ({hours_remaining:.0f}h > {MAX_HOURS_TO_RESOLUTION}h)",
        )
    return FilterResult(passed=True)


def run_all_filters(
    signal: SignalEvent,
    market: MarketMetadata,
    cash_balance: float,
    trade_params: TradeParams,
    open_positions: int,
    wallet_win_streak: int = 0,
) -> tuple[bool, SignalOutcome | None, dict[str, FilterResult]]:
    """
    Runs all 5 filters in order.
    Returns (all_passed, first_failure_reason, per_filter_results).
    """
    results: dict[str, FilterResult] = {}

    results["capital"] = filter_capital(
        cash_balance, trade_params.trade_size_usd, open_positions, trade_params.max_positions
    )
    results["lead_size"] = filter_lead_size(signal, trade_params.tier, wallet_win_streak)
    results["liquidity"] = filter_liquidity(market, signal, trade_params.tier)
    results["price_range"] = filter_price_range(signal)
    results["resolution_window"] = filter_resolution_window(market)

    for name, result in results.items():
        if not result.passed:
            return False, result.reason, results

    return True, None, results
