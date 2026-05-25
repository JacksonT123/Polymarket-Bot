"""
Goldsky Polymarket subgraphs (GraphQL, public, no auth).
Used for: ranking cross-validation, wash-trading audit, cluster detection.
NOT used for real-time trading decisions — too laggy (5-30s behind chain).
"""
from __future__ import annotations

import asyncio
from typing import Any

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.config import get_settings
from bot.observability.log import get_logger

log = get_logger(__name__)

_cfg = get_settings()
_BASE = _cfg.goldsky_base

SUBGRAPHS = {
    "pnl": f"{_BASE}/pnl-subgraph/0.0.14/gn",
    "positions": f"{_BASE}/positions-subgraph/0.0.7/gn",
    "orderbook": f"{_BASE}/orderbook-subgraph/0.0.1/gn",
    "activity": f"{_BASE}/activity-subgraph/0.0.4/gn",
    "oi": f"{_BASE}/oi-subgraph/0.0.6/gn",
}

_THE_GRAPH_FALLBACK = (
    f"https://gateway.thegraph.com/api/{_cfg.the_graph_api_key}"
    f"/subgraphs/id/Bx1W4S7kDVxs9gC3s2G6DS8kdNBJNVhMviCtin2DiBp"
    if _cfg.the_graph_api_key
    else None
)


def _make_client(url: str) -> Client:
    transport = AIOHTTPTransport(url=url, timeout=20)
    return Client(transport=transport, fetch_schema_from_transport=False)


# ── PnL subgraph ───────────────────────────────────────────────────────────────

_PNL_QUERY = gql("""
query WalletPnL($wallet: String!, $since: BigInt!) {
  userPositions(where: {user: $wallet, lastUpdated_gte: $since}, first: 1000) {
    id
    market { id }
    outcomeIndex
    totalBought
    totalSold
    netPositionSize
    realizedPnl
    realizedPnlPercentage
    lastUpdated
  }
}
""")

_TRADE_COUNT_QUERY = gql("""
query TradeCounts($wallets: [String!]!, $since: BigInt!) {
  orderFilledEvents(
    where: {transactor_in: $wallets, timestamp_gte: $since}
    first: 1000
    orderBy: timestamp
    orderDirection: desc
  ) {
    id
    transactor
    market { id }
    timestamp
    side
    pricePerShare
    sharesAmount
  }
}
""")


@retry(wait=wait_exponential(min=2, max=60), stop=stop_after_attempt(3))
async def get_wallet_pnl(proxy: str, since_ts: int) -> list[dict]:
    """Fetch closed-position PnL from the pnl subgraph for a wallet."""
    async with _make_client(SUBGRAPHS["pnl"]) as client:
        try:
            result = await client.execute_async(
                _PNL_QUERY,
                variable_values={"wallet": proxy.lower(), "since": str(since_ts)},
            )
            return result.get("userPositions", [])
        except Exception as e:
            log.warning("subgraph_pnl_failed", proxy=proxy, error=str(e))
            return []


@retry(wait=wait_exponential(min=2, max=60), stop=stop_after_attempt(3))
async def get_order_filled_events(wallets: list[str], since_ts: int) -> list[dict]:
    async with _make_client(SUBGRAPHS["orderbook"]) as client:
        try:
            result = await client.execute_async(
                _TRADE_COUNT_QUERY,
                variable_values={
                    "wallets": [w.lower() for w in wallets],
                    "since": str(since_ts),
                },
            )
            return result.get("orderFilledEvents", [])
        except Exception as e:
            log.warning("subgraph_orderbook_failed", error=str(e))
            return []


# ── Activity subgraph — splits, merges, redemptions ───────────────────────────

_ACTIVITY_QUERY = gql("""
query Activity($wallet: String!, $since: BigInt!) {
  activities(
    where: {user: $wallet, timestamp_gte: $since}
    first: 500
    orderBy: timestamp
    orderDirection: desc
  ) {
    id
    type
    market { id }
    timestamp
    amount
    shares
  }
}
""")


async def get_activity(proxy: str, since_ts: int) -> list[dict]:
    async with _make_client(SUBGRAPHS["activity"]) as client:
        try:
            result = await client.execute_async(
                _ACTIVITY_QUERY,
                variable_values={"wallet": proxy.lower(), "since": str(since_ts)},
            )
            return result.get("activities", [])
        except Exception as e:
            log.warning("subgraph_activity_failed", proxy=proxy, error=str(e))
            return []


# ── Open interest — liquidity gating ──────────────────────────────────────────

_OI_QUERY = gql("""
query MarketOI($market: String!) {
  markets(where: {id: $market}) {
    id
    outcomeTokenAmounts
    openInterest
  }
}
""")


async def get_market_open_interest(condition_id: str) -> dict | None:
    async with _make_client(SUBGRAPHS["oi"]) as client:
        try:
            result = await client.execute_async(
                _OI_QUERY,
                variable_values={"market": condition_id.lower()},
            )
            markets = result.get("markets", [])
            return markets[0] if markets else None
        except Exception as e:
            log.warning("subgraph_oi_failed", market=condition_id, error=str(e))
            return None
