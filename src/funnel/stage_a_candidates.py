"""Stage A: Pull top N wallets from leaderboard, enrich with lifetime stats."""
import asyncio
import structlog
from config.settings import CANDIDATE_POOL_SIZE
from src.data.polymarket_client import PolymarketClient

log = structlog.get_logger(__name__)


async def fetch_candidates(client: PolymarketClient, limit: int = CANDIDATE_POOL_SIZE) -> list[dict]:
    """
    Returns enriched wallet dicts with keys:
    address, alias, lifetime_pnl, total_volume, trades (list), positions (list)
    """
    log.info("stage_a_start", limit=limit)
    leaderboard = await client.get_leaderboard(limit=limit)
    log.info("stage_a_leaderboard_fetched", count=len(leaderboard))

    enriched: list[dict] = []
    sem = asyncio.Semaphore(10)  # limit concurrency

    async def enrich_wallet(entry: dict) -> dict | None:
        address = entry.get("proxyWallet") or entry.get("address") or entry.get("user")
        if not address:
            return None
        async with sem:
            try:
                trades = await client.get_wallet_trades(address, limit=500)
                positions = await client.get_wallet_positions(address, limit=500)
                return {
                    "address": address,
                    "alias": entry.get("name") or entry.get("displayName"),
                    "lifetime_pnl": float(entry.get("pnl", 0) or 0),
                    "total_volume": float(entry.get("volume", 0) or 0),
                    # leaderboard-level stats used as fallback in Stage B
                    "lb_win_rate": float(entry.get("winRate", 0) or 0),
                    "lb_trades_count": int(entry.get("tradesCount", 0) or entry.get("positionsCount", 0) or 0),
                    "trades": trades,
                    "positions": positions,
                }
            except Exception as e:
                log.warning("stage_a_enrich_failed", address=address, error=str(e))
                return None

    results = await asyncio.gather(*[enrich_wallet(e) for e in leaderboard])
    enriched = [r for r in results if r is not None]
    log.info("stage_a_complete", enriched=len(enriched))
    return enriched
