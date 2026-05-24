"""Stage D: Pick top N scored wallets for the shadow pool."""
import structlog
from config.settings import SHADOW_POOL_SIZE

log = structlog.get_logger(__name__)


def run_stage_d(scored_wallets: list[dict]) -> list[dict]:
    """Returns top SHADOW_POOL_SIZE wallets by composite score."""
    shadow_pool = scored_wallets[:SHADOW_POOL_SIZE]
    log.info("stage_d_complete",
             shadow_pool_size=len(shadow_pool),
             scores=[round(w.get("composite_score", 0), 2) for w in shadow_pool[:5]])
    return shadow_pool
