def estimate_slippage(market_volume_24h_usd: float, trade_size_usd: float) -> float | None:
    """
    Returns slippage as decimal (0.01 = 1%).
    Returns None if market fails Filter 3 (volume < $5,000).
    """
    if market_volume_24h_usd >= 500_000:
        base = 0.003
    elif market_volume_24h_usd >= 100_000:
        base = 0.005
    elif market_volume_24h_usd >= 50_000:
        base = 0.010
    elif market_volume_24h_usd >= 10_000:
        base = 0.020
    elif market_volume_24h_usd >= 5_000:
        base = 0.025
    else:
        return None

    size_pct = trade_size_usd / market_volume_24h_usd
    impact = max(0.0, (size_pct - 0.01) * 2.0)
    return base + impact
