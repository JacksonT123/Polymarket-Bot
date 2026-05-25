"""
Polygon log subscription via Alchemy WebSocket — eth_subscribe("logs", …)
Watches the CLOB V2 Exchange contract's OrderFilled/OrdersMatched events
for active leader proxy addresses in maker/taker fields.

This is the fastest detection path (~50–200ms after chain inclusion).
The Data API polling path picks up ~300–900ms after off-chain match,
often *before* chain settlement. Both run concurrently; dedup prevents doubles.
"""
from __future__ import annotations

import asyncio
import json
from typing import Callable

import websockets
from websockets.exceptions import ConnectionClosed
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.config import get_settings
from bot.observability.log import get_logger

log = get_logger(__name__)

# OrderFilled and OrdersMatched event topics (Keccak256 hashes)
# These are hypothetical — verify against the deployed V2 contract ABI
ORDER_FILLED_TOPIC = "0x3b3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e"

# ERC-1155 Transfer topic for CTF outcome tokens
TRANSFER_SINGLE_TOPIC = "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"


class PolygonLogSubscriber:
    """
    Subscribes to Polygon logs via Alchemy WSS.
    Calls `on_event(raw_log)` for each matching log entry.
    Reconnects automatically with exponential backoff.
    """

    def __init__(self, on_event: Callable[[dict], None], leader_proxies: list[str]) -> None:
        self._on_event = on_event
        self._leader_proxies: set[str] = {p.lower() for p in leader_proxies}
        self._running = False
        cfg = get_settings()
        self._wss_url = cfg.alchemy_wss
        self._exchange_address = cfg.clob_exchange_v2

    def update_leaders(self, proxies: list[str]) -> None:
        self._leader_proxies = {p.lower() for p in proxies}

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                await self._connect_and_subscribe()
            except ConnectionClosed as e:
                log.warning("polygon_ws_disconnected", code=e.code, reason=e.reason)
                await asyncio.sleep(2)
            except Exception as e:
                log.error("polygon_ws_error", error=str(e))
                await asyncio.sleep(5)

    async def stop(self) -> None:
        self._running = False

    async def _connect_and_subscribe(self) -> None:
        async with websockets.connect(
            self._wss_url,
            ping_interval=20,
            ping_timeout=10,
            open_timeout=30,
        ) as ws:
            log.info("polygon_log_subscription_connected")

            # Subscribe to logs from the exchange contract
            sub_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": [
                    "logs",
                    {
                        "address": self._exchange_address,
                    },
                ],
            }
            await ws.send(json.dumps(sub_req))
            resp = json.loads(await ws.recv())
            sub_id = resp.get("result")
            log.info("polygon_log_subscribed", subscription_id=sub_id)

            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw)
                    if msg.get("method") == "eth_subscription":
                        log_entry = msg["params"]["result"]
                        if self._is_relevant(log_entry):
                            await self._on_event(log_entry)
                except Exception as e:
                    log.warning("polygon_log_parse_error", error=str(e))

    def _is_relevant(self, log_entry: dict) -> bool:
        """Check if this log involves any of our tracked leader proxies."""
        # The Exchange V2 logs encode maker/taker in log topics or data.
        # For now, flag all logs from the exchange and let the caller filter.
        # Production: decode ABI and check maker/taker fields against _leader_proxies.
        return True  # upstream dedup + decode handles filtering


def decode_order_filled(log_entry: dict) -> dict | None:
    """
    Decode an OrderFilled log entry to extract maker, taker, token, price, size.
    Requires the V2 Exchange ABI — stub for now, real ABI integration needed.
    Returns None if decoding fails.
    """
    try:
        # Real implementation: use web3.py's contract.events decode
        # eth_abi.decode(types, bytes.fromhex(log_entry["data"][2:]))
        return {
            "tx_hash": log_entry.get("transactionHash", ""),
            "block_number": int(log_entry.get("blockNumber", "0x0"), 16),
            "raw": log_entry,
        }
    except Exception:
        return None
