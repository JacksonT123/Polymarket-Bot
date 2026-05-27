from __future__ import annotations

from bot.config import get_settings
from bot.models import CopyIntent, Side
from bot.observability.log import get_logger

log = get_logger(__name__)
_client = None


def _get_clob_client():
    global _client
    if _client is not None:
        return _client
    cfg = get_settings()
    if not cfg.live_ready:
        return None
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds

    kwargs: dict = {
        "host": cfg.clob_base_url,
        "key": cfg.polygon_private_key,
        "chain_id": cfg.chain_id,
        "signature_type": cfg.signature_type,
    }
    if cfg.polymarket_proxy_address:
        kwargs["funder"] = cfg.polymarket_proxy_address

    client = ClobClient(**kwargs)
    if cfg.clob_api_key and cfg.clob_api_secret and cfg.clob_api_passphrase:
        client.set_api_creds(
            ApiCreds(
                api_key=cfg.clob_api_key,
                api_secret=cfg.clob_api_secret,
                api_passphrase=cfg.clob_api_passphrase,
            )
        )
    else:
        client.set_api_creds(client.create_or_derive_api_creds())
    _client = client
    return client


async def post_live_order(intent: CopyIntent, price: float, shares: float) -> dict | None:
    cfg = get_settings()
    if not cfg.is_live or not cfg.live_ready:
        return None

    client = _get_clob_client()
    if client is None:
        return None

    from py_clob_client.clob_types import OrderArgs, OrderType
    from py_clob_client.order_builder.constants import BUY, SELL

    order_type = OrderType.FAK if cfg.order_type.upper() == "FAK" else OrderType.FOK
    side_const = BUY if intent.side == Side.BUY else SELL

    try:
        order = OrderArgs(
            token_id=str(intent.token_id),
            price=round(price, 4),
            size=round(shares, 4),
            side=side_const,
        )
        signed = client.create_order(order)
        resp = client.post_order(signed, order_type)
        order_id = resp.get("orderID") or resp.get("id") if isinstance(resp, dict) else str(resp)
        return {
            "status": "filled",
            "mode": "LIVE",
            "fill_price": price,
            "shares": shares,
            "notional": shares * price,
            "exchange_order_id": order_id,
        }
    except Exception as e:
        log.error("live_order_failed", error=str(e), event_id=intent.event_id)
        return {"status": "rejected", "reason": str(e)}
