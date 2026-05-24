from config.settings import COUNTER_TRADE_MIN_VOLUME_USD, COUNTER_TRADE_MAX_PNL_USD


def compute_counter_trade_signal(net_pnl_usd: float, total_volume_usd: float) -> tuple[float, bool]:
    """
    Returns (counter_trade_signal, is_counter_trade_candidate).
    High-volume consistent losers score -1.0 and are flagged as counter-trade candidates.
    """
    if net_pnl_usd < COUNTER_TRADE_MAX_PNL_USD and total_volume_usd > COUNTER_TRADE_MIN_VOLUME_USD:
        return -1.0, True
    return 0.0, False
