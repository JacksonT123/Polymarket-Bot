"""
Polymarket Gamma API client.
Base: https://gamma-api.polymarket.com
Market metadata, slugs, resolution dates, tick sizes.
"""
from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.config import get_settings
from bot.models import MarketInfo
from bot.observability.log import get_logger

log = get_logger(__name__)


class GammaClient:
    def __init__(self) -> None:
        cfg = get_settings()
        self._base = cfg.gamma_base_url
        self._client: httpx.AsyncClient | None = None
        self._market_cache: dict[str, MarketInfo] = {}

    async def __aenter__(self) -> "GammaClient":
        self._client = httpx.AsyncClient(base_url=self._base, timeout=15.0)
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(4))
    async def _get(self, path: str, params: dict | None = None) -> Any:
        assert self._client
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_market(self, condition_id: str) -> MarketInfo | None:
        if condition_id in self._market_cache:
            return self._market_cache[condition_id]
        try:
            data = await self._get(f"/markets/{condition_id}")
            info = _parse_market(data)
            self._market_cache[condition_id] = info
            return info
        except Exception as e:
            log.error("gamma_get_market_failed", condition_id=condition_id, error=str(e))
            return None

    async def get_markets(
        self,
        active: bool = True,
        closed: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MarketInfo]:
        params: dict[str, Any] = {"active": str(active).lower(), "limit": limit, "offset": offset}
        if closed:
            params["closed"] = "true"
        data = await self._get("/markets", params)
        markets = data if isinstance(data, list) else data.get("data", [])
        return [_parse_market(m) for m in markets]

    async def get_market_by_token(self, token_id: str) -> MarketInfo | None:
        """Find a market by YES or NO token ID."""
        for cached in self._market_cache.values():
            if cached.yes_token_id == token_id or cached.no_token_id == token_id:
                return cached
        try:
            data = await self._get("/markets", {"clob_token_ids": token_id})
            items = data if isinstance(data, list) else data.get("data", [])
            if not items:
                return None
            info = _parse_market(items[0])
            self._market_cache[info.condition_id] = info
            return info
        except Exception as e:
            log.error("gamma_get_by_token_failed", token_id=token_id, error=str(e))
            return None

    def get_cached(self, condition_id: str) -> MarketInfo | None:
        return self._market_cache.get(condition_id)


def _parse_market(data: dict) -> MarketInfo:
    tokens = data.get("tokens") or data.get("clobTokenIds") or []
    yes_token = ""
    no_token = ""
    if isinstance(tokens, list) and tokens:
        if isinstance(tokens[0], dict):
            yes_token = tokens[0].get("token_id", "")
            no_token = tokens[1].get("token_id", "") if len(tokens) > 1 else ""
        else:
            yes_token = tokens[0] if len(tokens) > 0 else ""
            no_token = tokens[1] if len(tokens) > 1 else ""

    return MarketInfo(
        condition_id=data.get("conditionId") or data.get("id", ""),
        yes_token_id=yes_token,
        no_token_id=no_token,
        question=data.get("question", ""),
        end_date_iso=data.get("endDate") or data.get("endDateIso", ""),
        tick_size=float(data.get("minimumTickSize") or data.get("tickSize") or 0.01),
        min_order_size=float(data.get("minSize") or data.get("minOrderSize") or 5),
        active=bool(data.get("active", True)),
        resolved=bool(data.get("closed", False) or data.get("resolved", False)),
    )
