def compute_profit_factor(resolved_trades: list[dict]) -> float:
    """Gross wins / gross losses. Capped at 10.0 when no losses."""
    wins  = sum(t["pnl"] for t in resolved_trades if t.get("pnl", 0) > 0)
    losses = abs(sum(t["pnl"] for t in resolved_trades if t.get("pnl", 0) < 0))
    if losses == 0:
        return 10.0
    return min(wins / losses, 10.0)
