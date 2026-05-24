"""Startup reconciliation: verify DB open positions match CLOB state."""
import structlog
from src.data.polymarket_client import get_client
from src.core.enums import PositionStatus
from src.db.repositories import PositionRepo

log = structlog.get_logger(__name__)


async def reconcile_positions(session) -> list[str]:
    """
    For every 'open' position in DB, verify CLOB says it exists.
    Returns list of position IDs flagged as RECONCILE_REQUIRED.
    Paper mode: always reconciles OK (no on-chain state to check).
    """
    from config.secrets import get_secrets
    if not get_secrets().is_live:
        log.info("reconciler_skipped", reason="paper_mode")
        return []

    repo = PositionRepo(session)
    open_positions = await repo.get_open(is_shadow=False)
    client = get_client()
    flagged: list[str] = []

    for pos in open_positions:
        try:
            price = await client.get_midpoint_price(pos.token_id)
            if price is None:
                log.warning("reconcile_position_not_found", position_id=pos.id,
                            token_id=pos.token_id)
                flagged.append(str(pos.id))
        except Exception as e:
            log.error("reconcile_error", position_id=pos.id, error=str(e))
            flagged.append(str(pos.id))

    if flagged:
        log.critical("reconcile_required", position_ids=flagged)
    else:
        log.info("reconcile_ok", checked=len(open_positions))

    return flagged
