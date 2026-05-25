"""
Daily discovery job: runs at 04:00 UTC, orchestrates the full funnel:
  gather_candidates → hard_filter → compute_candidate_stats → compute_wash_score
  → compute_scores → apply_survivorship → detect_clusters → build_roster → persist_roster
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from bot.data.data_api import DataAPIClient
from bot.discovery.antigaming import compute_wash_score, detect_clusters
from bot.discovery.candidates import gather_candidates
from bot.discovery.filters import filter_candidates
from bot.discovery.roster import apply_survivorship, build_roster, persist_roster
from bot.discovery.scoring import compute_candidate_stats, compute_scores
from bot.ledger import repo
from bot.observability.log import get_logger
from bot.observability.trace import new_trace

log = get_logger(__name__)

_WASH_CONCURRENCY = 5
_STATS_CONCURRENCY = 10


async def run_discovery() -> None:
    """Full discovery pipeline — top-level entry point."""
    new_trace()
    log.info("discovery_start")
    async with DataAPIClient() as client:
        await _run(client)


async def _run(client: DataAPIClient) -> None:
    # Step 1: gather candidates
    proxies = await gather_candidates(client)
    log.info("step1_complete", candidates=len(proxies))

    # Step 2: hard filter
    filter_results = await filter_candidates(proxies, client)
    passed_proxies = [p for p, reason in filter_results if reason is None]
    log.info("step2_complete", passed=len(passed_proxies))

    if not passed_proxies:
        log.warning("discovery_no_candidates_after_filter")
        return

    # Step 3: compute stats concurrently
    stats_sem = asyncio.Semaphore(_STATS_CONCURRENCY)
    candidates = []

    async def fetch_stats(proxy: str) -> None:
        async with stats_sem:
            c = await compute_candidate_stats(proxy, client)
            if c is not None:
                candidates.append(c)

    await asyncio.gather(*[fetch_stats(p) for p in passed_proxies])
    log.info("step3_complete", with_stats=len(candidates))

    if not candidates:
        log.warning("discovery_no_stats_computed")
        return

    # Step 4: wash scores concurrently
    wash_sem = asyncio.Semaphore(_WASH_CONCURRENCY)

    async def score_wash(c) -> None:
        async with wash_sem:
            c.wash_score = await compute_wash_score(c.proxy_address, client)

    await asyncio.gather(*[score_wash(c) for c in candidates])
    log.info("step4_complete", wash_scored=len(candidates))

    # Step 5: score candidates
    scored = compute_scores(candidates)
    log.info("step5_complete", scored=len(scored))

    # Step 6: survivorship guardrails
    surviving = apply_survivorship([c for c, _ in scored])
    surviving_addrs = {c.proxy_address for c in surviving}
    scored_surviving = [(c, s) for c, s in scored if c.proxy_address in surviving_addrs]
    log.info("step6_complete", surviving=len(scored_surviving))

    if not scored_surviving:
        log.warning("discovery_no_survivors")
        return

    # Step 7: cluster detection
    all_proxies = [c.proxy_address for c, _ in scored_surviving]
    cluster_map = await detect_clusters(all_proxies)
    log.info("step7_complete", clusters=len(set(cluster_map.values())))

    # Step 8: build roster
    prev_roster = await repo.get_roster()
    leaders = build_roster(scored_surviving, cluster_map, prev_roster)

    # Step 9: persist
    await persist_roster(leaders)
    log.info("discovery_complete", leaders=len(leaders))


async def schedule_daily_discovery() -> None:
    """
    Runs immediately once, then schedules itself every day at 04:00 UTC.
    Uses a simple asyncio loop rather than APScheduler to avoid deps.
    """
    log.info("discovery_scheduler_start")
    while True:
        try:
            await run_discovery()
        except Exception as e:
            log.error("discovery_job_error", error=str(e), exc_info=True)

        # Sleep until next 04:00 UTC
        now = datetime.now(tz=timezone.utc)
        next_run = now.replace(hour=4, minute=0, second=0, microsecond=0)
        if next_run <= now:
            from datetime import timedelta
            next_run += timedelta(days=1)
        sleep_seconds = (next_run - now).total_seconds()
        log.info("discovery_next_run", seconds=sleep_seconds)
        await asyncio.sleep(sleep_seconds)
