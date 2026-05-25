"""
CLOB market WebSocket channel — subscribes to `assets_ids` (token IDs).
Maintains an in-memory L2 book per market for the paper simulator.
Reconnects with exponential backoff. Server pings every 5s; we reply pong.
"""
from __future__ import annotations

import asyncio
import json
from typing import Callable

import websockets
from websockets.exceptions import ConnectionClosed

from bot.config import get_settings
from bot.models import BookLevel, OrderBook
from bot.observability.log import get_logger

log = get_logger(__name__)

# token_id → OrderBook
_books: dict[str, OrderBook] = {}


def get_book(token_id: str) -> OrderBook | None:
    return _books.get(token_id)


def get_all_books() -> dict[str, OrderBook]:
    return dict(_books)


class MarketWebSocket:
    """
    Maintains live L2 books for a set of token IDs.
    Provides `on_tick_size_change` callback to update market metadata.
    """

    def __init__(
        self,
        token_ids: list[str],
        on_tick_size_change: Callable[[str, float], None] | None = None,
    ) -> None:
        self._token_ids: set[str] = set(token_ids)
        self._on_tick_size_change = on_tick_size_change
        self._running = False
        cfg = get_settings()
        self._ws_url = cfg.clob_ws_market_url

    def subscribe(self, token_ids: list[str]) -> None:
        self._token_ids.update(token_ids)

    def unsubscribe(self, token_ids: list[str]) -> None:
        self._token_ids -= set(token_ids)

    async def run(self) -> None:
        self._running = True
        backoff = 1
        while self._running:
            try:
                await self._connect()
                backoff = 1
            except ConnectionClosed as e:
                log.warning("market_ws_disconnected", code=e.code, reason=e.reason)
            except Exception as e:
                log.error("market_ws_error", error=str(e))
            if self._running:
                await asyncio.sleep(min(backoff, 60))
                backoff = min(backoff * 2, 60)
                log.info("market_ws_reconnecting", backoff=backoff)

    async def stop(self) -> None:
        self._running = False

    async def _connect(self) -> None:
        async with websockets.connect(
            self._ws_url,
            ping_interval=None,  # we handle pong manually
            open_timeout=30,
        ) as ws:
            log.info("market_ws_connected")

            sub_msg = {
                "auth": {},
                "assets_ids": list(self._token_ids),
                "type": "Market",
            }
            await ws.send(json.dumps(sub_msg))

            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw)
                    await self._handle(msg, ws)
                except Exception as e:
                    log.warning("market_ws_parse_error", error=str(e))

    async def _handle(self, msg: dict | list, ws) -> None:
        if isinstance(msg, list):
            for item in msg:
                await self._handle(item, ws)
            return

        event_type = msg.get("event_type") or msg.get("type", "")

        if event_type == "ping":
            await ws.send(json.dumps({"type": "pong"}))
            return

        if event_type == "book":
            self._apply_book_snapshot(msg)
        elif event_type == "price_change":
            self._apply_price_change(msg)
        elif event_type == "tick_size_change":
            token_id = msg.get("asset_id", "")
            new_tick = float(msg.get("tick_size", 0.01))
            if self._on_tick_size_change and token_id:
                self._on_tick_size_change(token_id, new_tick)

    def _apply_book_snapshot(self, msg: dict) -> None:
        token_id = msg.get("asset_id", "")
        if not token_id:
            return
        bids = [BookLevel(float(b["price"]), float(b["size"])) for b in msg.get("bids", [])]
        asks = [BookLevel(float(a["price"]), float(a["size"])) for a in msg.get("asks", [])]
        bids.sort(key=lambda x: x.price, reverse=True)
        asks.sort(key=lambda x: x.price)
        _books[token_id] = OrderBook(
            token_id=token_id,
            market_id=msg.get("market_id", ""),
            bids=bids,
            asks=asks,
        )

    def _apply_price_change(self, msg: dict) -> None:
        token_id = msg.get("asset_id", "")
        book = _books.get(token_id)
        if not book:
            return
        changes = msg.get("changes", [])
        bid_map = {b.price: b for b in book.bids}
        ask_map = {a.price: a for a in book.asks}
        for change in changes:
            price = float(change["price"])
            size = float(change["size"])
            side = change.get("side", "")
            if side == "BUY":
                if size == 0:
                    bid_map.pop(price, None)
                else:
                    bid_map[price] = BookLevel(price, size)
            else:
                if size == 0:
                    ask_map.pop(price, None)
                else:
                    ask_map[price] = BookLevel(price, size)
        book.bids = sorted(bid_map.values(), key=lambda x: x.price, reverse=True)
        book.asks = sorted(ask_map.values(), key=lambda x: x.price)
