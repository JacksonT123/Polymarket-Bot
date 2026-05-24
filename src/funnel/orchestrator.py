"""Runs the full A→F funnel pipeline. Called daily by the runner."""
from datetime import datetime, timezone
import structlog

from src.data.polymarket_client import get_client
from src.funnel.stage_a_candidates import fetch_candidates
from src.funnel.stage_b_disqualifiers import run_stage_b
from src.funnel.stage_c_scoring import run_stage_c
from src.funnel.stage_d_ranking import run_stage_d
from src.funnel.stage_e_shadow import check_promotion_eligibility, check_suspension_triggers
from src.funnel.stage_f_active import select_active_wallets, should_permanently_drop
from src.core.enums import WalletStatus
from src.core.clock import now

log = structlog.get_logger(__name__)


async def run_funnel_pipeline(session, dry_run: bool = False) -> dict:
    """
    Runs the full funnel. If dry_run=True, logs results but does not write to DB.
    Returns a summary dict.
    """
    from src.db.repositories import WalletRepo
    from src.db.models import Wallet

    client = get_client()
    repo = WalletRepo(session)

    log.info("funnel_start", dry_run=dry_run)

    # ── Stage A ──────────────────────────────────────────────────────────────
    candidates = await fetch_candidates(client)
    log.info("stage_a_done", count=len(candidates))

    # ── Stage B ──────────────────────────────────────────────────────────────
    eligible, disqualified = run_stage_b(candidates)
    log.info("stage_b_done", eligible=len(eligible), disqualified=len(disqualified))

    # ── Stage C ──────────────────────────────────────────────────────────────
    scored = run_stage_c(eligible)
    log.info("stage_c_done", scored=len(scored))

    # ── Stage D ──────────────────────────────────────────────────────────────
    shadow_candidates = run_stage_d(scored)
    log.info("stage_d_done", shadow_candidates=len(shadow_candidates))

    if not dry_run:
        # Upsert all candidates into DB
        for w in disqualified:
            db_wallet = Wallet(
                address=w["address"],
                alias=w.get("alias"),
                status=WalletStatus.DISQUALIFIED.value,
                disqualified_reasons=w.get("dq_reasons", []),
            )
            _apply_stats(db_wallet, w.get("stats", {}))
            await repo.upsert(db_wallet)

        for w in shadow_candidates:
            existing = await repo.get_by_address(w["address"])
            if existing and existing.status in (WalletStatus.ACTIVE.value, WalletStatus.SUSPENDED.value):
                # Don't downgrade active/suspended wallets during daily refresh
                _apply_score_updates(existing, w)
                continue

            db_wallet = existing or Wallet(address=w["address"])
            db_wallet.alias = w.get("alias")
            if not existing or existing.status not in (WalletStatus.ACTIVE.value, WalletStatus.SUSPENDED.value):
                db_wallet.status = WalletStatus.SHADOW.value
                db_wallet.shadow_started_at = db_wallet.shadow_started_at or now()
            _apply_stats(db_wallet, w.get("stats", {}))
            _apply_score_updates(db_wallet, w)
            await repo.upsert(db_wallet)

        await session.commit()

    summary = {
        "candidates": len(candidates),
        "eligible": len(eligible),
        "disqualified": len(disqualified),
        "scored": len(scored),
        "shadow_candidates": len(shadow_candidates),
        "top_wallets": [
            {"address": w["address"], "score": round(w.get("composite_score", 0), 2)}
            for w in shadow_candidates[:5]
        ],
        "dq_breakdown": _tally_dq(disqualified),
    }
    log.info("funnel_complete", **{k: v for k, v in summary.items() if k != "top_wallets"})
    return summary


def _apply_stats(db_wallet, stats: dict) -> None:
    if not stats:
        return
    for field in (
        "win_rate", "closed_trades_count", "months_active", "primary_category",
        "category_diversity_count", "avg_holding_minutes", "max_drawdown_pct",
        "single_market_pnl_pct", "volume_5min_crypto_pct", "volume_15min_crypto_pct",
        "positive_roi_pct",
    ):
        val = stats.get(field)
        if val is not None:
            setattr(db_wallet, field, val)


def _apply_score_updates(db_wallet, w: dict) -> None:
    for field in (
        "composite_score", "win_rate_vs_category_floor_score", "profit_factor",
        "domain_score", "hold_to_resolution_pct", "consistency_score",
        "conviction_signal", "counter_trade_signal", "is_counter_trade_candidate",
        "crowding_score", "insider_proximity_score", "entropy_score", "primary_category",
    ):
        val = w.get(field)
        if val is not None:
            setattr(db_wallet, field, val)


def _tally_dq(disqualified: list[dict]) -> dict[str, int]:
    from collections import defaultdict
    tally: dict[str, int] = defaultdict(int)
    for w in disqualified:
        for r in w.get("dq_reasons", []):
            tally[r.split(":")[0]] += 1
    return dict(sorted(tally.items(), key=lambda x: -x[1]))
