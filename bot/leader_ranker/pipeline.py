from __future__ import annotations

from bot.config import get_settings
from bot.data.client import DataAPIClient
from bot.data.coordinator import run_discovery_guarded
from bot.leader_ranker.clusters import assign_clusters, pick_one_per_cluster
from bot.leader_ranker.scoring import build_candidate, score_candidates
from bot.ledger import repo
from bot.models import Leader
from bot.observability.log import get_logger

log = get_logger(__name__)


async def _discovery_impl(client: DataAPIClient) -> list[Leader]:
    cfg = get_settings()
    manual = [w.strip() for w in cfg.tracked_wallets.split(",") if w.strip()]
    if manual:
        leaders = [
            Leader(proxy=w, rank=i + 1, score=1.0 - i * 0.01, status="active")
            for i, w in enumerate(manual[: cfg.roster_active_size])
        ]
        await repo.upsert_leaders(leaders)
        return leaders

    if not cfg.auto_discover_leaders:
        return []

    proxies = await client.get_all_leaderboard_candidates(cfg.discovery_leaderboard_limit)
    log.info("discovery_candidates", count=len(proxies))

    candidates = []
    market_sets: dict[str, set[str]] = {}

    for proxy in proxies:
        c, markets = await build_candidate(client, proxy)
        if c:
            candidates.append(c)
            market_sets[proxy] = markets

    ranked = score_candidates(candidates)
    if not ranked:
        await repo.log_discovery_run(len(proxies), 0, 0, 0)
        return []

    cluster_map = assign_clusters(ranked, market_sets)
    deduped = pick_one_per_cluster(ranked, cluster_map)

    active_n = cfg.roster_active_size
    standby_n = cfg.roster_standby_size
    leaders: list[Leader] = []
    for i, c in enumerate(deduped[: active_n + standby_n]):
        status = "active" if i < active_n else "standby"
        leaders.append(
            Leader(
                proxy=c.proxy,
                rank=i + 1,
                score=c.score,
                pnl_30d=c.pnl_30d,
                win_rate=c.win_rate,
                trade_count_30d=c.trade_count_30d,
                status=status,
                cluster_id=cluster_map.get(c.proxy, ""),
            )
        )

    await repo.upsert_leaders(leaders)
    await repo.log_discovery_run(
        len(proxies), len(ranked), active_n, min(standby_n, max(0, len(leaders) - active_n))
    )
    log.info("discovery_complete", active=active_n, standby=len(leaders) - active_n)
    return [l for l in leaders if l.status == "active"]


async def run_discovery(client: DataAPIClient | None = None) -> list[Leader]:
    own_client = client is None
    if own_client:
        client = DataAPIClient()

    async def _run() -> list[Leader]:
        return await _discovery_impl(client)

    try:
        return await run_discovery_guarded(_run)
    finally:
        if own_client and client:
            await client.close()


async def get_active_leaders(client: DataAPIClient | None = None) -> list[Leader]:
    stored = await repo.get_leaders(status="active")
    stored = [r for r in stored if not str(r["proxy"]).startswith("demo_wallet_")]
    if stored:
        return [
            Leader(
                proxy=r["proxy"],
                rank=int(r["rank"]),
                score=float(r["score"]),
                pnl_30d=float(r.get("pnl_30d") or 0),
                win_rate=float(r.get("win_rate") or 0),
                trade_count_30d=int(r.get("trade_count_30d") or 0),
                status="active",
                cluster_id=str(r.get("cluster_id") or ""),
            )
            for r in stored
        ]
    return await run_discovery(client)
