from datetime import timedelta


def compute_hold_to_resolution_pct(closed_positions: list[dict]) -> float:
    """% of closed positions held until market resolution (2-hour buffer)."""
    if not closed_positions:
        return 0.0
    count = 0
    total = 0
    for pos in closed_positions:
        resolution_time = pos.get("market_resolution_time")
        closed_at = pos.get("closed_at")
        if resolution_time is None or closed_at is None:
            continue
        total += 1
        if closed_at >= resolution_time - timedelta(hours=2):
            count += 1
    return count / total if total > 0 else 0.0
