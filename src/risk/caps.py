"""Portfolio-level risk caps: deployment %, position count, daily new positions."""
import structlog
from config.settings import MAX_SAME_DAY_NEW_POSITIONS
from src.core.models import TradeParams

log = structlog.get_logger(__name__)


def check_portfolio_caps(
    trade_params: TradeParams,
    cash_balance: float,
    deployed_usd: float,
    open_positions: int,
    positions_opened_today: int,
    total_equity: float,
) -> tuple[bool, str | None]:
    """
    Returns (ok, reason_if_blocked).
    Checks: deployment %, position count, same-day limit.
    """
    # Max deployment %
    max_deploy = total_equity * trade_params.max_deployed_pct
    if deployed_usd + trade_params.trade_size_usd > max_deploy:
        return False, f"deployment_cap: {deployed_usd:.0f}+{trade_params.trade_size_usd:.0f} > {max_deploy:.0f}"

    # Max open positions
    if open_positions >= trade_params.max_positions:
        return False, f"position_cap: {open_positions}/{trade_params.max_positions}"

    # Max same-day new positions
    if positions_opened_today >= MAX_SAME_DAY_NEW_POSITIONS:
        return False, f"daily_new_cap: {positions_opened_today}/{MAX_SAME_DAY_NEW_POSITIONS}"

    return True, None
