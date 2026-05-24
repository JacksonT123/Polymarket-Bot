"""Stage E: Shadow mode validation — 21-day paper simulation before promotion."""
from datetime import datetime, timezone, timedelta
import structlog

from config.settings import (
    SHADOW_MODE_MIN_DAYS, SHADOW_MIN_SIMULATED_COPIES, SHADOW_MIN_CAPTURE_RATIO,
    SHADOW_MAX_SINGLE_LOSS_PCT, SHADOW_LEAD_WR_DRIFT_TOLERANCE, SHADOW_MAX_FAILED_CYCLES,
)
from src.core.enums import WalletStatus
from src.metrics.capture_ratio import compute_capture_ratio

log = structlog.get_logger(__name__)


def check_promotion_eligibility(wallet_db_row) -> tuple[bool, list[str]]:
    """
    Checks if a shadow wallet is eligible for promotion to active.
    Returns (eligible, list_of_failed_criteria).
    """
    failures: list[str] = []

    # Must have been in shadow at least SHADOW_MODE_MIN_DAYS
    if wallet_db_row.shadow_started_at:
        days_in_shadow = (datetime.now(timezone.utc) - wallet_db_row.shadow_started_at).days
        if days_in_shadow < SHADOW_MODE_MIN_DAYS:
            failures.append(f"insufficient_shadow_days:{days_in_shadow}/{SHADOW_MODE_MIN_DAYS}")

    # Must have at least N simulated copies
    if wallet_db_row.shadow_copies_count < SHADOW_MIN_SIMULATED_COPIES:
        failures.append(f"too_few_shadow_copies:{wallet_db_row.shadow_copies_count}/{SHADOW_MIN_SIMULATED_COPIES}")

    # Shadow P&L must be net positive
    if wallet_db_row.shadow_pnl_usd <= 0:
        failures.append(f"shadow_pnl_negative:{wallet_db_row.shadow_pnl_usd:.2f}")

    # Capture ratio must meet threshold
    capture = wallet_db_row.shadow_capture_ratio
    if capture is None or capture < SHADOW_MIN_CAPTURE_RATIO:
        failures.append(f"capture_ratio_below_floor:{capture}/{SHADOW_MIN_CAPTURE_RATIO}")

    return len(failures) == 0, failures


def check_suspension_triggers(wallet_db_row, recent_capture_ratio: float | None = None) -> list[str]:
    """
    Checks all active wallet suspension triggers.
    Returns list of triggered reasons (empty = no suspension needed).
    """
    from config.settings import (
        SUSPEND_CONSECUTIVE_LOSSES, SUSPEND_CAPTURE_RATIO_FLOOR,
        SUSPEND_LEAD_SILENT_DAYS, SUSPEND_CROWDING_SPIKE_PCT,
        DQ_MAX_TRADES_PER_DAY, DQ_MAX_CATEGORY_DIVERSITY,
    )
    triggers: list[str] = []

    if wallet_db_row.consecutive_losses_for_bot >= SUSPEND_CONSECUTIVE_LOSSES:
        triggers.append(f"consecutive_losses:{wallet_db_row.consecutive_losses_for_bot}")

    cap = recent_capture_ratio or wallet_db_row.recent_capture_ratio
    if cap is not None and cap < SUSPEND_CAPTURE_RATIO_FLOOR:
        triggers.append(f"capture_ratio_dropped:{cap:.2f}")

    if wallet_db_row.last_trade_at:
        silent_days = (datetime.now(timezone.utc) - wallet_db_row.last_trade_at).days
        if silent_days >= SUSPEND_LEAD_SILENT_DAYS:
            triggers.append(f"lead_silent:{silent_days}d")

    if wallet_db_row.crowding_score_baseline > 0 and wallet_db_row.crowding_score > 0:
        spike = (wallet_db_row.crowding_score - wallet_db_row.crowding_score_baseline) / wallet_db_row.crowding_score_baseline
        if spike > SUSPEND_CROWDING_SPIKE_PCT:
            triggers.append(f"crowding_spike:{spike:.0%}")

    return triggers
