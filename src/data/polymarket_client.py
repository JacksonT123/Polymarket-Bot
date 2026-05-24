"""Wraps the polymarket-apis SDK with rate limiting, caching, and retry logic."""
import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import aiohttp
import structlog

from src.core.exceptions import PolymarketAPIError, RateLimitError, AuthError
from src.core.models import MarketMetadata
from src.data.rate_limiter import get_rate_limiter
from src.data.cache import get_cache

log = structlog.get_logger(__name__)

DATA_API = "https://data-api.polymarket.com"
LB_API   = "https://lb-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API  = "https://clob.polymarket.com"

RETRY_CONFIG = {
    429: (5, "exp", 2.0, 60.0),   # retries, backoff, start_s, cap_s
    500: (3, "exp", 1.0, 30.0),
    502: (3, "exp", 1.0, 30.0),
    503: (3, "exp", 1.0, 30.0),
}


class PolymarketClient:
    def __init__(self):
        self._session: aiohttp.ClientSession | None = None
        self._rl = get_rate_limiter()
        self._cache = get_cache()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Accept": "application/json"},
            )
        return self._session

    async def _get(self, url: str, rl_key: str, params: dict | None = None) -> Any:
        await self._rl.acquire(rl_key)
        session = await self._get_session()

        last_exc: Exception | None = None
        cfg = RETRY_CONFIG.get(0, (1, "none", 0, 0))
        max_retries = 1

        for attempt in range(max_retries + 1):
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status in (401, 403):
                        raise AuthError(f"Auth error {resp.status} on {url}", resp.status)
                    retry_cfg = RETRY_CONFIG.get(resp.status)
                    if retry_cfg and attempt < retry_cfg[0]:
                        wait = min(retry_cfg[2] * (2 ** attempt), retry_cfg[3])
                        log.warning("api_retry", url=url, status=resp.status, attempt=attempt, wait=wait)
                        await asyncio.sleep(wait)
                        continue
                    raise PolymarketAPIError(
                        f"HTTP {resp.status} from {url}", resp.status
                    )
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
                last_exc = e
                if attempt < 2:
                    await asyncio.sleep(5.0 * (2 ** attempt))
                    continue
                raise PolymarketAPIError(f"Connection error: {e}") from e

        raise PolymarketAPIError(f"Exhausted retries for {url}") from last_exc

    # ─── Data API ────────────────────────────────────────────────────────────

    async def get_leaderboard(self, limit: int = 100) -> list[dict]:
        # lb-api.polymarket.com caps at 100 per request; fetch profit leaderboard
        data = await self._get(
            f"{LB_API}/profit",
            "data.leaderboard",
            params={"window": "all", "limit": min(limit, 100)},
        )
        return data if isinstance(data, list) else data.get("data", [])

    async def get_wallet_trades(self, address: str, limit: int = 500, offset: int = 0) -> list[dict]:
        data = await self._get(
            f"{DATA_API}/trades",
            "data.trades",
            params={"user": address, "limit": limit, "offset": offset},
        )
        return data if isinstance(data, list) else data.get("data", [])

    async def get_wallet_positions(self, address: str, limit: int = 500) -> list[dict]:
        data = await self._get(
            f"{DATA_API}/positions",
            "data.positions",
            params={"user": address, "limit": limit},
        )
        return data if isinstance(data, list) else data.get("data", [])

    async def get_wallet_activity(self, address: str, limit: int = 20) -> list[dict]:
        data = await self._get(
            f"{DATA_API}/activity",
            "data.activity",
            params={"user": address, "limit": limit},
        )
        return data if isinstance(data, list) else data.get("data", [])

    # ─── Gamma API ───────────────────────────────────────────────────────────

    async def get_market_metadata(self, condition_id: str) -> MarketMetadata:
        cached = self._cache.market_metadata.get(condition_id)
        if cached:
            return cached

        # Gamma API uses query param, not path param; returns a list
        raw = await self._get(
            f"{GAMMA_API}/markets",
            "gamma.markets",
            params={"condition_id": condition_id},
        )
        data = raw[0] if isinstance(raw, list) and raw else (raw if isinstance(raw, dict) else {})

        end_date = None
        for date_field in ("endDateIso", "end_date_iso", "endDate", "end_date"):
            val = data.get(date_field)
            if val:
                try:
                    dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    end_date = dt
                    break
                except ValueError:
                    continue

        # clobTokenIds is a JSON-encoded string in the API response
        import json as _json
        clob_ids = data.get("clobTokenIds") or data.get("clob_token_ids") or "[]"
        if isinstance(clob_ids, str):
            try:
                clob_ids = _json.loads(clob_ids)
            except Exception:
                clob_ids = []

        meta = MarketMetadata(
            condition_id=condition_id,
            question=data.get("question", ""),
            category=_normalize_category(data.get("category_slug") or data.get("categorySlug") or ""),
            volume_24h_usd=float(data.get("volume24hr") or data.get("volume_num_24hr") or data.get("volume24hrClob") or 0),
            end_date=end_date,
            is_closed=data.get("closed", False) or data.get("archived", False),
            yes_token_id=clob_ids[0] if len(clob_ids) > 0 else "",
            no_token_id=clob_ids[1] if len(clob_ids) > 1 else "",
        )
        self._cache.market_metadata.set(condition_id, meta)
        return meta

    async def get_market_volume(self, condition_id: str) -> float:
        meta = await self.get_market_metadata(condition_id)
        return meta.volume_24h_usd

    # ─── CLOB API ─────────────────────────────────────────────────────────────

    async def get_midpoint_price(self, token_id: str) -> float | None:
        try:
            data = await self._get(
                f"{CLOB_API}/midpoint",
                "clob.read",
                params={"token_id": token_id},
            )
            return float(data.get("mid", 0)) or None
        except PolymarketAPIError:
            return None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


def _normalize_category(slug: str) -> str:
    """Map Polymarket category slugs to our internal category names."""
    slug = (slug or "").lower()
    mapping = {
        "soccer": "soccer", "football": "soccer",
        "politics": "politics", "elections": "politics",
        "geopolitics": "geopolitics", "world": "geopolitics",
        "weather": "weather",
        "nfl": "sports_us", "nba": "sports_us", "mlb": "sports_us",
        "baseball": "sports_us", "basketball": "sports_us",
        "crypto": "crypto", "cryptocurrency": "crypto",
        "finance": "finance", "economy": "macro", "macro": "macro",
        "pop-culture": "culture", "culture": "culture",
        "tech": "tech", "technology": "tech",
        "science": "tech",
    }
    for key, cat in mapping.items():
        if key in slug:
            return cat
    return "_default"


_client: PolymarketClient | None = None


def get_client() -> PolymarketClient:
    global _client
    if _client is None:
        _client = PolymarketClient()
    return _client
