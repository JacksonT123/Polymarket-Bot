import os
from config.settings import (
    PAPER_INITIAL_BALANCE, TIER_TABLE,
    SHADOW_MODE_MIN_DAYS, SHADOW_POOL_SIZE, ACTIVE_POOL_SIZE, SHADOW_MIN_CAPTURE_RATIO,
    DQ_MIN_WIN_RATE, DQ_MIN_CLOSED_TRADES, DQ_MAX_DRAWDOWN_PCT,
    W_LOG_TRADES, W_WIN_RATE_VS_CATEGORY_FLOOR, W_LOG_PROFIT_FACTOR, W_MONTHS_ACTIVE,
    W_DOMAIN_SCORE, W_HOLD_TO_RESOLUTION_PCT, W_CONSISTENCY_SCORE, W_CONVICTION_SIGNAL,
    W_ENTROPY, W_INSIDER_PROXIMITY, W_MAX_DRAWDOWN, W_CROWDING_PENALTY,
    CATEGORY_WIN_RATE_FLOORS, MAX_BUY_SLIPPAGE_PCT, MAX_SELL_SLIPPAGE_PCT,
    MIN_PRICE, MAX_PRICE, MIN_HOURS_TO_RESOLUTION, MAX_HOURS_TO_RESOLUTION,
)
from src.core.enums import TradingMode
from src.core.exceptions import ConfigValidationError


def validate_config() -> None:
    """Verifies every config value is sensible. Raises ConfigValidationError on failure."""
    errors: list[str] = []

    def check(condition: bool, msg: str) -> None:
        if not condition:
            errors.append(msg)

    # Capital
    check(0 < PAPER_INITIAL_BALANCE <= 1_000_000, f"PAPER_INITIAL_BALANCE={PAPER_INITIAL_BALANCE} out of range")
    check(TIER_TABLE[0]["min_bankroll"] <= PAPER_INITIAL_BALANCE,
          "TIER_TABLE[0].min_bankroll must be <= PAPER_INITIAL_BALANCE")

    # Tier table ordering
    for i in range(len(TIER_TABLE) - 1):
        check(TIER_TABLE[i]["min_bankroll"] < TIER_TABLE[i + 1]["min_bankroll"],
              f"TIER_TABLE not strictly ascending at index {i}")

    # Shadow
    check(0 < SHADOW_MODE_MIN_DAYS <= 90, f"SHADOW_MODE_MIN_DAYS={SHADOW_MODE_MIN_DAYS} out of range")
    check(0 < SHADOW_POOL_SIZE <= 100, f"SHADOW_POOL_SIZE={SHADOW_POOL_SIZE} out of range")
    check(0 < ACTIVE_POOL_SIZE <= SHADOW_POOL_SIZE,
          "ACTIVE_POOL_SIZE must be > 0 and <= SHADOW_POOL_SIZE")
    check(0 < SHADOW_MIN_CAPTURE_RATIO <= 1.0,
          f"SHADOW_MIN_CAPTURE_RATIO={SHADOW_MIN_CAPTURE_RATIO} out of range")

    # Disqualifiers
    check(0 < DQ_MIN_WIN_RATE < 1.0, f"DQ_MIN_WIN_RATE={DQ_MIN_WIN_RATE} out of range")
    check(DQ_MIN_CLOSED_TRADES > 0, "DQ_MIN_CLOSED_TRADES must be > 0")
    check(0 < DQ_MAX_DRAWDOWN_PCT < 1.0, f"DQ_MAX_DRAWDOWN_PCT={DQ_MAX_DRAWDOWN_PCT} out of range")

    # Scoring weights
    positive = [W_LOG_TRADES, W_WIN_RATE_VS_CATEGORY_FLOOR, W_LOG_PROFIT_FACTOR,
                W_MONTHS_ACTIVE, W_DOMAIN_SCORE, W_HOLD_TO_RESOLUTION_PCT,
                W_CONSISTENCY_SCORE, W_CONVICTION_SIGNAL]
    check(0.8 <= sum(positive) <= 1.5,
          f"Positive scoring weights sum={sum(positive):.3f} should be 0.8–1.5")

    negative = [W_ENTROPY, W_INSIDER_PROXIMITY, W_MAX_DRAWDOWN, W_CROWDING_PENALTY]
    check(-0.5 <= sum(negative) <= 0,
          f"Negative scoring weights sum={sum(negative):.3f} should be -0.5–0")

    # Category floors
    for cat, floor in CATEGORY_WIN_RATE_FLOORS.items():
        check(0.5 <= floor <= 0.9, f"Category floor for '{cat}'={floor} out of [0.5, 0.9]")

    # Execution
    check(0 < MAX_BUY_SLIPPAGE_PCT < 0.3, f"MAX_BUY_SLIPPAGE_PCT={MAX_BUY_SLIPPAGE_PCT} out of range")
    check(0 < MAX_SELL_SLIPPAGE_PCT < 0.3, f"MAX_SELL_SLIPPAGE_PCT={MAX_SELL_SLIPPAGE_PCT} out of range")
    check(MIN_PRICE < MAX_PRICE, "MIN_PRICE must be < MAX_PRICE")
    check(MIN_HOURS_TO_RESOLUTION < MAX_HOURS_TO_RESOLUTION,
          "MIN_HOURS_TO_RESOLUTION must be < MAX_HOURS_TO_RESOLUTION")

    # Live mode requires credentials
    from config.secrets import get_secrets
    secrets = get_secrets()
    if secrets.trading_mode == TradingMode.LIVE:
        check(bool(secrets.polymarket_private_key), "LIVE mode requires POLYMARKET_PRIVATE_KEY")
        check(bool(secrets.polymarket_api_key), "LIVE mode requires POLYMARKET_API_KEY")
        check(bool(secrets.polymarket_api_secret), "LIVE mode requires POLYMARKET_API_SECRET")
        check(bool(secrets.polymarket_api_passphrase), "LIVE mode requires POLYMARKET_API_PASSPHRASE")
        check(bool(secrets.polymarket_proxy_address), "LIVE mode requires POLYMARKET_PROXY_ADDRESS")

    if errors:
        msg = "Config validation failed:\n" + "\n".join(f"  • {e}" for e in errors)
        raise ConfigValidationError(msg)
