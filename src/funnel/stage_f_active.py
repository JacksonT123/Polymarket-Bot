"""Stage F: Select up to 5 active wallets from shadow-passers; manage bench."""
import structlog
from config.settings import ACTIVE_POOL_SIZE, SHADOW_MAX_FAILED_CYCLES
from src.core.enums import WalletStatus

log = structlog.get_logger(__name__)


def compute_promotion_score(wallet_db_row) -> float:
    """Promotion Score = composite_score × capture_ratio × signal_count_factor."""
    composite = wallet_db_row.composite_score or 0.0
    capture = wallet_db_row.shadow_capture_ratio or 0.0
    copies = wallet_db_row.shadow_copies_count or 0
    # signal_count_factor: scale copies to [0.5, 1.5], more = better
    signal_factor = min(1.5, max(0.5, copies / 50))
    return composite * capture * signal_factor


def select_active_wallets(shadow_passers: list) -> tuple[list, list]:
    """
    Returns (active_wallets, bench_wallets) from validated shadow pool passers.
    Sorted by promotion score descending.
    """
    scored = sorted(shadow_passers, key=compute_promotion_score, reverse=True)
    max_active = ACTIVE_POOL_SIZE
    active = scored[:max_active]
    bench = scored[max_active:]
    log.info("stage_f_selection", active=len(active), bench=len(bench))
    return active, bench


def should_permanently_drop(wallet_db_row) -> bool:
    """Second suspension within 60 days → permanent drop."""
    return wallet_db_row.shadow_failed_cycles >= SHADOW_MAX_FAILED_CYCLES
