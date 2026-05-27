from __future__ import annotations

import asyncio
import time
from typing import Any

import certifi
import httpx

from bot.config import get_settings
from bot.data import rate_limit
from bot.models import LeaderTradeEvent, Side
from bot.observability.log import get_logger

log = get_logger(__name__)


class DataAPIClient:
    def __init__(self) -> None:
        cfg = get_settings()
        verify: bool | str = certifi.where() if cfg.ssl_verify else False
        self._http = httpx.AsyncClient(
            base_url=cfg.data_api_base_url,
            timeout=25.0,
            verify=verify,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str, params: dict | None = None) -> Any:
        last_err: Exception | None = None
        saw_429 = False
        max_attempts = 3
        for attempt in range(max_attempts):
            await rate_limit.wait_turn()
            try:
                r = await self._http.get(path, params=params or {})
                if r.status_code == 429:
                    saw_429 = True
                    pause = rate_limit.penalize_429(attempt)
                    log.warning(
                        "data_api_rate_limited",
                        path=path,
                        pause_sec=round(pause, 1),
                        attempt=attempt + 1,
                    )
                    if attempt + 1 >= max_attempts:
                        break
                    await asyncio.sleep(pause)
                    continue
                r.raise_for_status()
                rate_limit.note_success()
                return r.json()
            except httpx.HTTPStatusError as e:
                last_err = e
                if e.response.status_code == 429:
                    saw_429 = True
                    pause = rate_limit.penalize_429(attempt)
                    if attempt + 1 >= max_attempts:
                        break
                    await asyncio.sleep(pause)
                    continue
                if attempt + 1 < max_attempts:
                    await asyncio.sleep(0.5 * (attempt + 1))
            except Exception as e:
                last_err = e
                if attempt + 1 < max_attempts:
                    await asyncio.sleep(0.5 * (attempt + 1))
        if saw_429:
            from bot.engine import status as engine_status

            engine_status.record_api_error("rate_limited_429")
            return []
        if last_err:
            from bot.engine import status as engine_status

            engine_status.record_api_error(str(last_err)[:120])
            log.warning("data_api_request_failed", path=path, error=str(last_err)[:120])
        return []

    async def get_leaderboard(self, *, limit: int = 50, offset: int = 0, time_period: str = "MONTH") -> list[dict]:
        try:
            data = await self._get(
                "/v1/leaderboard",
                {"limit": limit, "offset": offset, "timePeriod": time_period},
            )
            if isinstance(data, list) and data:
                return data
            if isinstance(data, dict):
                rows = data.get("data") or data.get("leaderboard") or data.get("users") or []
                if rows:
                    return rows
        except Exception as e:
            log.warning("leaderboard_fetch_failed", offset=offset, error=str(e))
        return []

    async def get_all_leaderboard_candidates(self, max_wallets: int = 200) -> list[str]:
        proxies: list[str] = []
        offset = 0
        page_size = 50
        while offset < max_wallets:
            page = await self.get_leaderboard(limit=page_size, offset=offset)
            if not page:
                break
            for row in page:
                proxy = (
                    row.get("proxyWallet")
                    or row.get("proxy_wallet")
                    or row.get("address")
                    or row.get("user")
                )
                if proxy and proxy not in proxies:
                    proxies.append(str(proxy))
            if len(page) < page_size:
                break
            offset += page_size
            await asyncio.sleep(0.8)
        return proxies[:max_wallets]

    async def get_activity(self, user: str, *, limit: int = 100, activity_type: str = "TRADE") -> list[dict]:
        data = await self._get(
            "/activity",
            {
                "user": user,
                "type": activity_type,
                "limit": limit,
                "sortBy": "TIMESTAMP",
                "sortDirection": "DESC",
            },
        )
        return data if isinstance(data, list) else []

    async def get_trades(self, user: str, *, limit: int = 500) -> list[dict]:
        data = await self._get("/trades", {"user": user, "limit": limit})
        return data if isinstance(data, list) else []

    async def get_positions(self, user: str, *, limit: int = 200) -> list[dict]:
        data = await self._get(
            "/positions",
            {"user": user, "limit": limit, "sortBy": "CURRENT", "sortDirection": "DESC"},
        )
        return data if isinstance(data, list) else []

    async def estimate_bankroll_usd(self, user: str) -> float:
        positions = await self.get_positions(user, limit=100)
        total = 0.0
        for p in positions:
            try:
                total += float(p.get("currentValue") or p.get("value") or 0)
            except (TypeError, ValueError):
                continue
        if total > 10:
            return total
        trades = await self.get_trades(user, limit=50)
        if not trades:
            return 0.0
        notionals = []
        for t in trades:
            try:
                n = float(t.get("usdcSize") or 0)
                if n <= 0:
                    n = float(t.get("size", 0)) * float(t.get("price", 0))
                if n > 0:
                    notionals.append(n)
            except (TypeError, ValueError):
                continue
        if not notionals:
            return 0.0
        return max(sum(notionals) * 2.0, max(notionals) * 5.0)

    def parse_trade_events(self, wallet: str, rows: list[dict]) -> list[LeaderTradeEvent]:
        events: list[LeaderTradeEvent] = []
        for t in rows:
            try:
                side_raw = str(t.get("side", "")).upper()
                if side_raw not in ("BUY", "SELL"):
                    continue
                side = Side(side_raw)
                condition = str(t.get("conditionId") or t.get("condition_id") or "")
                if not condition:
                    continue
                token_id = str(t.get("asset") or t.get("tokenId") or t.get("outcomeIndex") or "")
                price = float(t.get("price", 0))
                usdc = float(t.get("usdcSize") or 0)
                if usdc <= 0 and price > 0:
                    usdc = float(t.get("size", 0)) * price
                if price <= 0 or usdc <= 0:
                    continue
                ts = int(t.get("timestamp", 0) or time.time())
                tx = str(t.get("transactionHash") or t.get("txHash") or "")
                eid = f"{wallet}:{tx}:{ts}:{condition}:{side}:{usdc:.4f}"
                events.append(
                    LeaderTradeEvent(
                        event_id=eid,
                        leader_proxy=wallet,
                        condition_id=condition,
                        token_id=token_id,
                        side=side,
                        price=price,
                        usdc_size=usdc,
                        timestamp=ts,
                        tx_hash=tx,
                        outcome=str(t.get("outcome") or ""),
                    )
                )
            except Exception:
                continue
        return events

    async def get_recent_trade_events(self, wallet: str, limit: int = 25) -> list[LeaderTradeEvent]:
        rows = await self.get_activity(wallet, limit=limit)
        return self.parse_trade_events(wallet, rows)
