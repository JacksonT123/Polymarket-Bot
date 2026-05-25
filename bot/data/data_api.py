"""
Polymarket Data API client.
Base: https://data-api.polymarket.com
All endpoints are public, no auth required.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.config import get_settings
from bot.observability.log import get_logger

log = get_logger(__name__)


class DataAPIClient:
    def __init__(self) -> None:
        cfg = get_settings()
        self._base = cfg.data_api_base_url
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "DataAPIClient":
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=15.0,
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(4))
    async def _get(self, path: str, params: dict | None = None) -> Any:
        assert self._client, "Use as async context manager"
        resp = await self._client.get(path, params=params)
        if resp.status_code == 429:
            log.warning("rate_limit_hit", path=path)
            await asyncio.sleep(5)
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json()

    async def get_trades(
        self,
        user: str,
        limit: int = 20,
        market: str | None = None,
        side: str | None = None,
        taker_only: bool = True,
    ) -> list[dict]:
        params: dict[str, Any] = {"user": user, "limit": limit, "takerOnly": str(taker_only).lower()}
        if market:
            params["market"] = market
        if side:
            params["side"] = side
        data = await self._get("/trades", params)
        return data if isinstance(data, list) else data.get("data", [])

    async def get_positions(
        self,
        user: str,
        limit: int = 100,
        sort_by: str = "CURRENT",
        size_threshold: float | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {"user": user, "limit": limit, "sortBy": sort_by}
        if size_threshold is not None:
            params["sizeThreshold"] = size_threshold
        data = await self._get("/positions", params)
        return data if isinstance(data, list) else data.get("data", [])

    async def get_value(self, user: str) -> float:
        data = await self._get("/value", {"user": user})
        if isinstance(data, list) and data:
            return float(data[0].get("value", 0))
        if isinstance(data, dict):
            return float(data.get("value", 0))
        return 0.0

    async def get_activity(
        self,
        user: str,
        start: int | None = None,
        end: int | None = None,
        limit: int = 200,
    ) -> list[dict]:
        params: dict[str, Any] = {"user": user, "limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        data = await self._get("/activity", params)
        return data if isinstance(data, list) else data.get("data", [])

    async def get_leaderboard(
        self,
        category: str = "OVERALL",
        time_period: str = "WEEK",
        order_by: str = "PNL",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        params = {
            "category": category,
            "timePeriod": time_period,
            "orderBy": order_by,
            "limit": limit,
            "offset": offset,
        }
        data = await self._get("/v1/leaderboard", params)
        return data if isinstance(data, list) else data.get("data", [])

    async def get_holders(self, market: str) -> list[dict]:
        data = await self._get("/holders", {"market": market})
        return data if isinstance(data, list) else data.get("data", [])

    async def get_all_leaderboard_pages(
        self,
        category: str = "OVERALL",
        time_period: str = "WEEK",
        order_by: str = "PNL",
        max_offset: int = 500,
    ) -> list[dict]:
        """Paginate through leaderboard up to max_offset=500 wallets."""
        results: list[dict] = []
        offset = 0
        while offset <= max_offset:
            page = await self.get_leaderboard(
                category=category,
                time_period=time_period,
                order_by=order_by,
                limit=50,
                offset=offset,
            )
            if not page:
                break
            results.extend(page)
            if len(page) < 50:
                break
            offset += 50
            await asyncio.sleep(0.2)
        return results


async def poll_leader_trades(
    leader_proxy: str,
    last_seen_tx: str | None,
    client: DataAPIClient,
) -> list[dict]:
    """Fetch new trades for a leader since last_seen_tx. Returns newest-first."""
    trades = await client.get_trades(user=leader_proxy, limit=20)
    if not last_seen_tx:
        return trades
    new_trades = []
    for t in trades:
        if t.get("transactionHash") == last_seen_tx:
            break
        new_trades.append(t)
    return new_trades
