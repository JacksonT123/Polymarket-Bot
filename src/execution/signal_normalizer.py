"""Normalizes raw Polymarket /activity API responses into internal SignalEvent objects."""
from datetime import datetime, timezone
import structlog
from src.core.models import SignalEvent
from src.core.enums import SignalDirection

log = structlog.get_logger(__name__)


def normalize_activity(raw: dict, wallet_address: str, is_shadow: bool = False) -> SignalEvent | None:
    """
    Converts a single /activity item into a SignalEvent.
    Returns None if the event is not a trade we care about.
    """
    # type field: "TRADE" = buy/sell, "REDEEM" = collect winnings (skip), etc.
    event_type = (raw.get("type") or "").upper()
    if event_type and event_type not in ("TRADE",):
        return None  # silently skip REDEEMs — not actionable

    # direction: side field is always BUY/SELL on real activity events
    action = (raw.get("side") or raw.get("action") or "").upper()
    if action not in ("BUY", "SELL"):
        log.info("normalize_drop", wallet=wallet_address[:10], reason="not_a_trade",
                 action=action, event_type=event_type, keys=list(raw.keys()))
        return None

    market_id = raw.get("conditionId") or raw.get("market_id") or raw.get("marketId")
    token_id = raw.get("asset") or raw.get("tokenId") or raw.get("token_id") or ""
    side = _infer_side(raw)
    price = float(raw.get("price", 0) or raw.get("fillPrice", 0) or 0)
    value_usd = float(raw.get("amount", 0) or raw.get("value", 0) or raw.get("usdcSize", 0) or 0)

    if not market_id or price <= 0:
        log.info("normalize_drop", wallet=wallet_address[:10], reason="missing_market_or_price",
                 market_id=market_id, price=price)
        return None

    ts = raw.get("timestamp") or raw.get("created_at")
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    elif isinstance(ts, (int, float)):
        ts = datetime.fromtimestamp(ts, tz=timezone.utc)
    elif ts is None:
        ts = datetime.now(timezone.utc)

    return SignalEvent(
        wallet_address=wallet_address,
        market_id=market_id,
        token_id=token_id,
        side=side,
        direction=SignalDirection.BUY if action == "BUY" else SignalDirection.SELL,
        price=price,
        value_usd=value_usd,
        lead_timestamp=ts,
        detected_at=datetime.now(timezone.utc),
        is_shadow=is_shadow,
        raw=raw,
    )


def _infer_side(raw: dict) -> str:
    """Infer YES/NO from token outcome field."""
    outcome = (raw.get("outcome") or raw.get("outcomeIndex") or "").upper()
    if isinstance(raw.get("outcomeIndex"), int):
        return "YES" if raw["outcomeIndex"] == 0 else "NO"
    if "YES" in outcome or outcome == "0":
        return "YES"
    if "NO" in outcome or outcome == "1":
        return "NO"
    return "YES"  # default
