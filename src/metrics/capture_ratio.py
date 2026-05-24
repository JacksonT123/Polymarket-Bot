from typing import Any


def compute_capture_ratio(
    bot_copies: list[dict],
    lead_trades: list[dict],
) -> float | None:
    """
    ROI-normalized capture ratio: bot_roi / lead_roi.
    Returns None if insufficient data or lead ROI is zero.
    """
    bot_pnl = sum(c.get("realized_pnl_usd", 0) + c.get("unrealized_pnl_usd", 0) for c in bot_copies)
    lead_pnl = sum(t.get("realized_pnl_usd", 0) + t.get("unrealized_pnl_usd", 0) for t in lead_trades)

    bot_invested = sum(c.get("cost_usd", 0) for c in bot_copies)
    lead_invested = sum(t.get("cost_usd", 0) for t in lead_trades)

    if lead_invested == 0 or bot_invested == 0:
        return None

    bot_roi = bot_pnl / bot_invested
    lead_roi = lead_pnl / lead_invested

    if lead_roi == 0:
        return None

    return bot_roi / lead_roi
