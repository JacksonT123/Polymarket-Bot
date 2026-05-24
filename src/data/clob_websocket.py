"""
Polymarket Live Data WebSocket — real-time global trade feed.

Architecture:
- Connects to wss://ws-live-data.polymarket.com and subscribes to the global activity feed.
- Every trade on the platform is broadcast with proxyWallet included in the payload.
- We filter against tracked lead wallets and push matches to the urgent_queue for
  immediate HTTP poll — giving sub-100ms detection vs 2–5s periodic sweep.
- register() signature is unchanged so poller.py needs no edits; condition_id and
  token_id args are accepted but not used (wallet address is all we need).
- Auto-reconnects with exponential backoff, capping at 5 minutes.
"""
import asyncio
import json
import structlog
import aiohttp

log = structlog.get_logger(__name__)

LIVE_DATA_WS_URL = "wss://ws-live-data.polymarket.com"
_SUBSCRIBE_MSG = {"action": "subscribe", "subscriptions": [{"type": "activity"}]}


class CLOBWebSocket:
    def __init__(self) -> None:
        self._wallets: set[str] = set()        # lowercased lead wallet addresses
        self._wallet_map: dict[str, str] = {}  # lower → original casing
        self._urgent: asyncio.Queue | None = None
        self._running = False
        self._connected = False

    # ── Public API ──────────────────────────────────────────────────────────

    def set_urgent_queue(self, q: asyncio.Queue) -> None:
        self._urgent = q

    def register(self, wallet: str, condition_id: str, token_id: str) -> None:
        """Register a lead wallet to watch for live trades."""
        lower = wallet.lower()
        self._wallet_map[lower] = wallet
        self._wallets.add(lower)

    def is_connected(self) -> bool:
        return self._connected

    def stop(self) -> None:
        self._running = False

    # ── Main loop ───────────────────────────────────────────────────────────

    async def run(self) -> None:
        self._running = True
        backoff = 5.0
        while self._running:
            try:
                await self._connect_and_listen()
                backoff = 5.0
            except Exception as e:
                self._connected = False
                log.info("ws_disconnected", error=str(e)[:80], reconnect_s=round(backoff))
            if self._running:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 300.0)

    async def _connect_and_listen(self) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                LIVE_DATA_WS_URL,
                heartbeat=20,
                timeout=aiohttp.ClientWSTimeout(ws_close=10),
            ) as ws:
                self._connected = True
                log.info("ws_live_data_connected", tracking_wallets=len(self._wallets))

                await ws.send_json(_SUBSCRIBE_MSG)

                async for msg in ws:
                    if not self._running:
                        break
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._handle(msg.data)
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break

                self._connected = False

    # ── Message handling ────────────────────────────────────────────────────

    async def _handle(self, data: str) -> None:
        if self._urgent is None:
            return
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            return

        if not isinstance(event, dict):
            return

        if event.get("type") not in ("trades", "orders_matched"):
            return

        payload = event.get("payload")
        if not isinstance(payload, dict):
            return

        proxy_wallet = (payload.get("proxyWallet") or "").lower()
        if not proxy_wallet or proxy_wallet not in self._wallets:
            return

        original = self._wallet_map[proxy_wallet]
        await self._urgent.put(original)
        log.debug("ws_trade_detected", wallet=original[:10])


# ── Singleton ────────────────────────────────────────────────────────────────

_instance: CLOBWebSocket | None = None


def get_clob_ws() -> CLOBWebSocket:
    global _instance
    if _instance is None:
        _instance = CLOBWebSocket()
    return _instance
