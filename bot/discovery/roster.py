"""
Roster management: takes scored candidates, applies survivorship guardrails,
deduplicates clusters, and produces the final ranked active/standby list.
"""
from __future__ import annotations

import time
from datetime import date

from bot.config import get_settings
from bot.ledger import repo
from bot.models import Leader, LeaderCandidate, LeaderStatus, LeaderTier
from bot.observability.log import get_logger

log = get_logger(__name__)

# Survivorship guardrails (§2.5)
_MIN_CLOSED_TRADES = 30
_MIN_ACCOUNT_AGE_DAYS = 21
_MAX_DRAWDOWN_30D = 0.35
_WASH_SCORE_THRESHOLD = 0.30


def apply_survivorship(candidates: list[LeaderCandidate]) -> list[LeaderCandidate]:
    """Drop candidates that fail survivorship guardrails."""
    kept = []
    for c in candidates:
        if c.wash_score > _WASH_SCORE_THRESHOLD:
            log.info("candidate_dropped_wash", proxy=c.proxy_address, score=c.wash_score)
            continue
        if c.trades_30d < _MIN_CLOSED_TRADES:
            log.info("candidate_dropped_trades", proxy=c.proxy_address, trades=c.trades_30d)
            continue
        if c.realized_pnl_30d <= 0:
            log.info("candidate_dropped_negative_pnl", proxy=c.proxy_address)
            continue
        kept.append(c)
    return kept


def build_roster(
    scored: list[tuple[LeaderCandidate, float]],
    cluster_map: dict[str, str],
    prev_roster: list[Leader],
) -> list[Leader]:
    """
    Build today's roster from scored candidates.
    - Deduplicates cluster siblings (keep highest scorer).
    - Top N=active_size become active; next M=standby_size become standby.
    - Carries over score_delta vs yesterday's roster.
    """
    cfg = get_settings()
    today = str(date.today())

    # Build previous score map for delta
    prev_scores: dict[str, float] = {l.proxy_address: l.score for l in prev_roster}

    # Cluster dedup: keep only the best-scoring wallet per cluster
    seen_clusters: dict[str, str] = {}  # canonical_proxy → best_proxy
    deduped: list[tuple[LeaderCandidate, float]] = []
    for c, score in scored:
        canonical = cluster_map.get(c.proxy_address, c.proxy_address)
        if canonical not in seen_clusters:
            seen_clusters[canonical] = c.proxy_address
            deduped.append((c, score))

    leaders: list[Leader] = []
    for rank, (c, score) in enumerate(deduped, start=1):
        tier = (
            LeaderTier.ACTIVE
            if rank <= cfg.roster_active_size
            else LeaderTier.STANDBY
        )
        if rank > cfg.roster_active_size + cfg.roster_standby_size:
            break

        prev_score = prev_scores.get(c.proxy_address, score)
        delta = score - prev_score

        leaders.append(
            Leader(
                proxy_address=c.proxy_address,
                rank=rank,
                tier=tier,
                score=round(score, 6),
                score_delta=round(delta, 6),
                status=LeaderStatus.ACTIVE,
                cold_since_ts=None,
                snapshot_date=today,
            )
        )

    log.info(
        "roster_built",
        active=sum(1 for l in leaders if l.tier is LeaderTier.ACTIVE),
        standby=sum(1 for l in leaders if l.tier is LeaderTier.STANDBY),
    )
    return leaders


async def persist_roster(leaders: list[Leader]) -> None:
    await repo.upsert_roster(leaders)
    log.info("roster_persisted", date=leaders[0].snapshot_date if leaders else "")
