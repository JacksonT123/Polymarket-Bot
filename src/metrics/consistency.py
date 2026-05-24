import statistics
from collections import defaultdict
from datetime import datetime, timezone


def compute_consistency_score(resolved_trades: list[dict]) -> float:
    """
    Coefficient of variation of monthly P&L. Lower CV = more consistent = higher score.
    Returns 0.5 (neutral) if fewer than 3 months of data.
    """
    monthly: dict[str, float] = defaultdict(float)
    for t in resolved_trades:
        ts = t.get("resolved_at") or t.get("timestamp")
        if not ts or t.get("pnl") is None:
            continue
        if isinstance(ts, (int, float)):
            ts = datetime.fromtimestamp(ts, tz=timezone.utc)
        elif isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
        if not isinstance(ts, datetime):
            continue
        key = f"{ts.year}-{ts.month:02d}"
        monthly[key] += t["pnl"]

    monthly_returns = list(monthly.values())
    if len(monthly_returns) < 3:
        return 0.5

    mean_return = statistics.mean(monthly_returns)
    if mean_return <= 0:
        return 0.0

    std_dev = statistics.stdev(monthly_returns)
    cv = std_dev / mean_return
    return max(0.0, 1.0 - (cv / 2.0))
