from datetime import timedelta


def compute_insider_proximity_score(
    recent_trades: list[dict],
    news_events: list[dict] | None = None,
) -> float:
    """
    Penalty for trading before news breaks. Requires Polysights news event dataset.
    Returns 0.0 when data unavailable (safe default).
    """
    if not news_events:
        return 0.0

    suspicious = 0
    for trade in recent_trades:
        trade_ts = trade.get("timestamp")
        market_id = trade.get("market_id")
        if not trade_ts or not market_id:
            continue
        for event in news_events:
            if event.get("market_id") != market_id:
                continue
            event_ts = event.get("timestamp")
            if not event_ts:
                continue
            window_end = trade_ts + timedelta(hours=6)
            if trade_ts < event_ts <= window_end:
                suspicious += 1
                break

    return min(1.0, suspicious / 10)
