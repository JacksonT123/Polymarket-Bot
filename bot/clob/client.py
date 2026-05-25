"""
Thin wrapper over py-clob-client-v2.
Lazy-imports the SDK so the rest of the bot can run without it installed
(paper-only mode, data layer, dashboard).

Install: uv pip install "py-clob-client-v2 @ git+https://github.com/Polymarket/py-clob-client-v2"
"""
from __future__ import annotations

from typing import Any

from bot.config import get_settings
from bot.observability.log import get_logger
from bot.security.keystore import require_secret

log = get_logger(__name__)


class ClobClientWrapper:
    """
    Wraps py-clob-client-v2's ClobClient.
    Initialized lazily — call `await init()` before use.
    """

    def __init__(self) -> None:
        self._client: Any = None

    async def init(self) -> None:
        cfg = get_settings()
        try:
            from py_clob_client.client import ClobClient  # type: ignore[import]
        except ImportError:
            raise RuntimeError(
                "py-clob-client-v2 not installed.\n"
                "Run: uv pip install 'py-clob-client-v2 @ git+https://github.com/Polymarket/py-clob-client-v2'"
            )

        private_key = require_secret(cfg.keyring_service_eoa_key)
        api_key = require_secret(cfg.keyring_service_clob_api)
        api_secret = require_secret(cfg.keyring_service_clob_secret)
        api_passphrase = require_secret(cfg.keyring_service_clob_passphrase)

        self._client = ClobClient(
            host=cfg.clob_base_url,
            chain_id=cfg.chain_id,
            private_key=private_key,
            funder=cfg.bot_proxy_address,
            api_creds={
                "apiKey": api_key,
                "apiSecret": api_secret,
                "apiPassphrase": api_passphrase,
            },
        )
        log.info("clob_client_initialized")

    async def create_or_derive_api_key(self) -> dict:
        assert self._client, "Call init() first"
        return self._client.create_or_derive_api_key()

    async def create_and_post_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        order_type: str = "FOK",
        client_order_id: str | None = None,
    ) -> dict:
        """
        Place a FOK order on the CLOB V2.
        side: "BUY" | "SELL"
        Returns the CLOB response dict.
        """
        assert self._client, "Call init() first"
        from py_clob_client.order_builder.constants import BUY, SELL  # type: ignore[import]
        from py_clob_client.clob_types import OrderArgs, OrderType  # type: ignore[import]

        side_const = BUY if side == "BUY" else SELL
        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=side_const,
            order_type=OrderType.FOK,
        )
        if client_order_id:
            order_args.client_order_id = client_order_id

        signed_order = self._client.create_order(order_args)
        response = self._client.post_order(signed_order, OrderType.FOK)
        log.info(
            "order_submitted",
            token_id=token_id,
            price=price,
            size=size,
            side=side,
            response=response,
        )
        return response

    async def get_order(self, order_id: str) -> dict | None:
        assert self._client
        try:
            return self._client.get_order(order_id)
        except Exception as e:
            log.warning("get_order_failed", order_id=order_id, error=str(e))
            return None

    async def cancel_order(self, order_id: str) -> dict:
        assert self._client
        return self._client.cancel_order({"orderID": order_id})

    async def get_market(self, condition_id: str) -> dict | None:
        assert self._client
        try:
            return self._client.get_market(condition_id)
        except Exception as e:
            log.warning("get_market_failed", condition_id=condition_id, error=str(e))
            return None

    async def get_order_book(self, token_id: str) -> dict | None:
        assert self._client
        try:
            return self._client.get_order_book(token_id)
        except Exception as e:
            log.warning("get_book_failed", token_id=token_id, error=str(e))
            return None


# Module-level singleton — init() called in bot/main.py at startup
clob_client = ClobClientWrapper()
