"""
CoinGecko free API — USDC reference price sanity check.
30 calls/minute free, no API key required.
"""
from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.observability.log import get_logger

log = get_logger(__name__)

_BASE = "https://api.coingecko.com/api/v3"


@retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(3))
async def get_usdc_price() -> float:
    """Returns USDC/USD price. Should be very close to 1.0."""
    async with httpx.AsyncClient(base_url=_BASE, timeout=10.0) as client:
        resp = await client.get(
            "/simple/price",
            params={"ids": "usd-coin", "vs_currencies": "usd"},
        )
        resp.raise_for_status()
        data = resp.json()
        price = float(data.get("usd-coin", {}).get("usd", 1.0))
        if abs(price - 1.0) > 0.02:
            log.warning("usdc_depeg_detected", price=price)
        return price
