"""GET /api/leaders — active roster and candidate history."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from bot.ledger import repo
from bot.ledger.db import get_db

router = APIRouter()


async def _enrich_roster() -> list[dict]:
    """Return roster rows joined with candidate stats."""
    leaders = await repo.get_roster()

    # Pull win_rate, realized_pnl_30d, trades_30d from candidates table
    proxies = [l.proxy_address for l in leaders]
    stats: dict[str, dict] = {}
    if proxies:
        placeholders = ",".join("?" * len(proxies))
        async with get_db() as db:
            async with db.execute(
                f"""SELECT proxy_address, win_rate, realized_pnl_30d, trades_30d, wash_score
                    FROM leader_candidates WHERE proxy_address IN ({placeholders})""",
                proxies,
            ) as cur:
                rows = await cur.fetchall()
        for r in rows:
            stats[r[0]] = {
                "win_rate": r[1],
                "roi": (r[2] / (r[3] * 5.0)) if r[3] and r[3] > 0 else None,  # rough ROI estimate
                "total_volume_usd": r[3] * 5.0 if r[3] else None,  # trades × avg base
                "active_markets": None,
            }

    return [
        {
            "proxy_address": l.proxy_address,
            "rank": l.rank,
            "score": l.score,
            "score_delta": l.score_delta,
            "snapshot_date": l.snapshot_date,
            "is_active": l.tier.value == "active" and l.status.value == "active",
            "roi": stats.get(l.proxy_address, {}).get("roi"),
            "win_rate": stats.get(l.proxy_address, {}).get("win_rate"),
            "total_volume_usd": stats.get(l.proxy_address, {}).get("total_volume_usd"),
            "active_markets": stats.get(l.proxy_address, {}).get("active_markets"),
        }
        for l in leaders
    ]


@router.get("")
async def get_leaders() -> list[dict]:
    return await _enrich_roster()


@router.get("/{proxy}")
async def get_leader_detail(proxy: str) -> dict:
    enriched = await _enrich_roster()
    match = next((l for l in enriched if l["proxy_address"] == proxy), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Leader not found")

    signals = await repo.get_signals_for_leader(proxy, limit=50)
    return {"leader": match, "recent_signals": signals}
