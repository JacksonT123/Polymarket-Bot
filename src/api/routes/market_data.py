"""External data proxy routes — market enrichment, news, crypto prices."""
import asyncio
import aiohttp
import structlog
from fastapi import APIRouter, Query

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/data", tags=["market-data"])

GAMMA_API  = "https://gamma-api.polymarket.com"
CLOB_API   = "https://clob.polymarket.com"
COINGECKO  = "https://api.coingecko.com/api/v3"
GDELT_API  = "https://api.gdeltproject.org/api/v2"

_TIMEOUT = aiohttp.ClientTimeout(total=8)


async def _get(url: str, params: dict | None = None) -> dict | list | None:
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.get(url, params=params) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
    except Exception as e:
        log.warning("external_fetch_failed", url=url, err=str(e))
    return None


# ─── Market metadata ──────────────────────────────────────────────────────────

@router.get("/market")
async def market_info(condition_id: str = Query(...)):
    """Get human-readable market title, category, end date from Polymarket gamma."""
    raw = await _get(f"{GAMMA_API}/markets", {"condition_id": condition_id})
    if not raw:
        return {"question": "", "category": "", "end_date": None, "volume_24h": 0}
    m = raw[0] if isinstance(raw, list) and raw else raw
    return {
        "question":   m.get("question", ""),
        "category":   m.get("categorySlug") or m.get("category_slug", ""),
        "end_date":   m.get("endDateIso") or m.get("endDate"),
        "volume_24h": float(m.get("volume24hr") or m.get("volume_num_24hr") or 0),
        "active":     not m.get("closed", False),
    }


@router.get("/markets/active")
async def active_markets(limit: int = Query(20, le=50)):
    """Top active Polymarket markets by 24h volume."""
    raw = await _get(f"{GAMMA_API}/markets", {
        "active": "true", "closed": "false",
        "limit": str(limit), "order": "volume24hr", "ascending": "false",
    })
    if not raw:
        return []
    rows = raw if isinstance(raw, list) else raw.get("data", [])
    return [
        {
            "condition_id": m.get("conditionId", ""),
            "question":     m.get("question", ""),
            "category":     m.get("categorySlug", ""),
            "volume_24h":   float(m.get("volume24hr") or 0),
            "end_date":     m.get("endDateIso"),
        }
        for m in rows[:limit]
    ]


@router.get("/price")
async def token_price(token_id: str = Query(...)):
    """Live midpoint price for a CLOB token."""
    raw = await _get(f"{CLOB_API}/midpoint", {"token_id": token_id})
    if not raw:
        return {"mid": None}
    return {"mid": float(raw.get("mid", 0)) or None}


@router.get("/prices/bulk")
async def prices_bulk(token_ids: str = Query(..., description="comma-separated token IDs")):
    """Live prices for multiple tokens in one shot."""
    ids = [t.strip() for t in token_ids.split(",") if t.strip()][:20]
    tasks = [_get(f"{CLOB_API}/midpoint", {"token_id": tid}) for tid in ids]
    results = await asyncio.gather(*tasks)
    return {
        tid: (float(r.get("mid", 0)) if r else None)
        for tid, r in zip(ids, results)
    }


# ─── Crypto prices ────────────────────────────────────────────────────────────

@router.get("/crypto")
async def crypto_prices():
    """MATIC, ETH, USDC prices from CoinGecko free tier (no key required)."""
    raw = await _get(f"{COINGECKO}/simple/price", {
        "ids": "matic-network,ethereum,tether",
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_last_updated_at": "true",
    })
    if not raw:
        return {}
    return {
        "matic": {
            "usd":    raw.get("matic-network", {}).get("usd"),
            "change": raw.get("matic-network", {}).get("usd_24h_change"),
        },
        "eth": {
            "usd":    raw.get("ethereum", {}).get("usd"),
            "change": raw.get("ethereum", {}).get("usd_24h_change"),
        },
        "usdc": {
            "usd":    raw.get("tether", {}).get("usd"),
            "change": raw.get("tether", {}).get("usd_24h_change"),
        },
    }


# ─── News feed ────────────────────────────────────────────────────────────────

@router.get("/news")
async def news_feed(
    query: str = Query("polymarket prediction market", description="Search terms"),
    limit: int = Query(15, le=25),
):
    """
    News articles via GDELT 2.0 DOC API — completely free, no key required.
    Useful for understanding market context around copy-traded positions.
    """
    raw = await _get(f"{GDELT_API}/doc/doc", {
        "query":      query,
        "mode":       "artlist",
        "maxrecords": str(limit),
        "format":     "json",
        "sort":       "date",
    })
    if not raw:
        return []
    articles = raw.get("articles", [])
    return [
        {
            "title":  a.get("title", ""),
            "url":    a.get("url", ""),
            "domain": a.get("domain", ""),
            "date":   a.get("seendate", ""),
            "tone":   round(float(a.get("tone", 0) or 0), 2),
        }
        for a in articles[:limit]
        if a.get("title") and a.get("url")
    ]
