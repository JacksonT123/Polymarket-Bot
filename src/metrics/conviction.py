import statistics


def compute_conviction_signal(resolved_trades: list[dict]) -> float:
    """
    Median size of winning trades vs losing trades.
    Ratio > 1 means the wallet bets bigger on its winners — real conviction.
    Scaled to [0, 1]: ratio 1.0 → 0.0, ratio 3.0+ → 1.0.
    """
    wins   = [t["size_usd"] for t in resolved_trades if t.get("pnl", 0) > 0 and t.get("size_usd")]
    losses = [t["size_usd"] for t in resolved_trades if t.get("pnl", 0) < 0 and t.get("size_usd")]

    if not wins or not losses:
        return 0.5

    avg_winner = statistics.median(wins)
    avg_loser  = statistics.median(losses)

    if avg_loser == 0:
        return 1.0

    ratio = avg_winner / avg_loser
    return min(1.0, max(0.0, (ratio - 1.0) / 2.0))
