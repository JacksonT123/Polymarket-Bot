import statistics
from config.settings import CATEGORY_WIN_RATE_FLOORS, DQ_MIN_WIN_RATE


def compute_win_rate(resolved_trades: list[dict]) -> float:
    """Win rate over resolved trades only."""
    resolved = [t for t in resolved_trades if t.get("resolved", False)]
    if not resolved:
        return 0.0
    wins = sum(1 for t in resolved if t.get("pnl", 0) > 0)
    return wins / len(resolved)


def get_category_floor(category: str) -> float:
    floor = CATEGORY_WIN_RATE_FLOORS.get(category, CATEGORY_WIN_RATE_FLOORS["_default"])
    return max(floor, DQ_MIN_WIN_RATE)


def compute_win_rate_vs_category_floor(win_rate: float | None, category: str) -> float:
    """Excess win rate above category-specific floor, scaled to [0, 1]."""
    if win_rate is None:
        return 0.5  # neutral score when insufficient data
    floor = get_category_floor(category)
    excess = max(0.0, win_rate - floor)
    return min(1.0, excess / 0.15)
