"""
CLOB user WebSocket — tracks OUR OWN fills and orders only.
Uses L2 credentials (apiKey, HMAC).
Reports `trade` and `order` events for our proxy wallet.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Callable

import websockets
from websockets.exceptions import ConnectionClosed

from bot.config import get_settings
from bot.observability.log import get_logger
from bot.security.keystore import require_secret

log = get_logger(__name__)


class UserWebSocket:
    """
    Subscribes to the CLOB user channel for our own fills.
    Calls `on_fill(event)` whenever a trade event arrives.
    """

    def __init__(
        self,
        market_condition_ids: list[str],
        on_fill: Callable[[dict], None],
    ) -> None:
        self._markets = list(market_condition_ids)
        self._on_fill = on_fill
        self._running = False
        cfg = get_settings()
        self._ws_url = cfg.clob_ws_user_url

    def add_markets(self, condition_ids: list[str]) -> None:
        self._markets.extend(condition_ids)

    async def run(self) -> None:
        self._running = True
        backoff = 1
        while self._running:
            try:
                await self._connect()
                backoff = 1
            except ConnectionClosed as e:
                log.warning("user_ws_disconnected", code=e.code, reason=e.reason)
            except Exception as e:
                log.error("user_ws_error", error=str(e))
            if self._running:
                await asyncio.sleep(min(backoff, 60))
                backoff = min(backoff * 2, 60)

    async def stop(self) -> None:
        self._running = False

    async def _connect(self) -> None:
        cfg = get_settings()
        api_key = require_secret(cfg.keyring_service_clob_api)
        api_secret = require_secret(cfg.keyring_service_clob_secret)
        api_passphrase = require_secret(cfg.keyring_service_clob_passphrase)

        import hmac, hashlib, base64
        ts = str(int(time.time() * 1000))
        msg = ts + "GET" + "/ws/user"
        sig = base64.b64encode(
            hmac.new(api_secret.encode(), msg.encode(), hashlib.sha256).digest()
        ).decode()

        headers = {
            "POLY_ADDRESS": cfg.bot_proxy_address,
            "POLY_SIGNATURE": sig,
            "POLY_TIMESTAMP": ts,
            "POLY_API_KEY": api_key,
            "POLY_PASSPHRASE": api_passphrase,
        }

        async with websockets.connect(
            self._ws_url, additional_headers=headers, open_timeout=30
        ) as ws:
            log.info("user_ws_connected")
            sub = {"auth": {}, "markets": self._markets, "type": "User"}
            await ws.send(json.dumps(sub))

            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg_data = json.loads(raw)
                    if isinstance(msg_data, list):
                        for ev in msg_data:
                            self._handle(ev)
                    else:
                        self._handle(msg_data)
                except Exception as e:
                    log.warning("user_ws_parse_error", error=str(e))

    def _handle(self, event: dict) -> None:
        event_type = event.get("event_type") or event.get("type", "")
        if event_type == "trade":
            log.info("own_fill_received", event=event)
            self._on_fill(event)
        elif event_type == "order":
            log.info("own_order_update", event=event)
