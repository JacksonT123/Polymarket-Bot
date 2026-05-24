"""
Wallet activity polling — three concurrent loops + WebSocket fast lane.

Loop architecture:
  _active_loop   — polls active wallets every ACTIVE_WALLET_POLL_S (2 s)
  _shadow_loop   — polls shadow wallets every ACTIVITY_POLL_S (5 s)
  _urgent_loop   — drains a queue fed by the CLOB WebSocket; polls immediately
                   when WS detects a trade in a subscribed market (~250 ms latency)

The WS subscriber handles its own reconnection and feeds _urgent_queue.
HTTP sweeps run regardless of WS state — they are the backstop.
"""
import asyncio
import time
from datetime import datetime, timezone
import structlog

from config.settings import ACTIVITY_POLL_S, ACTIVE_WALLET_POLL_S
from src.data.polymarket_client import get_client
from src.data.clob_websocket import get_clob_ws
from src.execution.signal_normalizer import normalize_activity
from src.execution.queue import get_signal_queue

log = structlog.get_logger(__name__)

_URGENT_DEDUP_S = 1.0   # ignore duplicate urgent polls within this window


class WalletPoller:
    def __init__(self) -> None:
        self._client = get_client()
        self._queue = get_signal_queue()
        self._last_seen: dict[str, datetime] = {}
        self._running = False

        self._urgent_queue: asyncio.Queue[str] = asyncio.Queue()
        self._urgent_last: dict[str, float] = {}   # wallet → monotonic time of last urgent poll

        self._active_set: set[str] = set()
        self._shadow_set: set[str] = set()

        ws = get_clob_ws()
        ws.set_urgent_queue(self._urgent_queue)

    # ── Entry point ─────────────────────────────────────────────────────────

    async def run(self, get_active_wallets, get_shadow_wallets) -> None:
        self._running = True
        ws = get_clob_ws()
        log.info("poller_started", active_s=ACTIVE_WALLET_POLL_S, shadow_s=ACTIVITY_POLL_S)

        await asyncio.gather(
            ws.run(),
            self._urgent_loop(),
            self._active_loop(get_active_wallets),
            self._shadow_loop(get_shadow_wallets),
            return_exceptions=True,
        )

    # ── WebSocket fast lane ─────────────────────────────────────────────────

    async def _urgent_loop(self) -> None:
        while self._running:
            try:
                wallet = await asyncio.wait_for(self._urgent_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            now = time.monotonic()
            if now - self._urgent_last.get(wallet, 0) < _URGENT_DEDUP_S:
                continue  # skip: already polled this wallet very recently via WS
            self._urgent_last[wallet] = now

            is_shadow = wallet in self._shadow_set
            try:
                await self._poll_wallet(wallet, is_shadow)
                log.debug("ws_fast_poll", wallet=wallet[:10], is_shadow=is_shadow)
            except Exception as e:
                log.warning("urgent_poll_error", wallet=wallet[:10], error=str(e))

    # ── Periodic HTTP sweeps ─────────────────────────────────────────────────

    async def _active_loop(self, get_active_wallets) -> None:
        while self._running:
            try:
                active = get_active_wallets()
                if asyncio.iscoroutine(active):
                    active = await active
                self._active_set = set(active)
                if active:
                    tasks = [self._poll_wallet(addr, False) for addr in active]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for r in results:
                        if isinstance(r, Exception):
                            log.warning("active_poll_error", error=str(r))
            except Exception as e:
                log.error("active_loop_error", error=str(e))
            await asyncio.sleep(ACTIVE_WALLET_POLL_S)

    async def _shadow_loop(self, get_shadow_wallets) -> None:
        while self._running:
            try:
                shadow = get_shadow_wallets()
                if asyncio.iscoroutine(shadow):
                    shadow = await shadow
                self._shadow_set = set(shadow)
                if shadow:
                    tasks = [self._poll_wallet(addr, True) for addr in shadow]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for r in results:
                        if isinstance(r, Exception):
                            log.warning("shadow_poll_error", error=str(r))
            except Exception as e:
                log.error("shadow_loop_error", error=str(e))
            await asyncio.sleep(ACTIVITY_POLL_S)

    # ── Core poll ────────────────────────────────────────────────────────────

    async def _poll_wallet(self, wallet_address: str, is_shadow: bool) -> None:
        try:
            activities = await self._client.get_wallet_activity(wallet_address, limit=50)
        except Exception as e:
            log.warning("activity_fetch_failed", address=wallet_address[:10], error=str(e))
            return

        ws = get_clob_ws()
        last_seen = self._last_seen.get(wallet_address)
        new_signals = []
        dropped_normalize = 0
        dropped_seen = 0

        for activity in activities:
            signal = normalize_activity(activity, wallet_address, is_shadow=is_shadow)
            if signal is None:
                dropped_normalize += 1
                continue
            if last_seen and signal.lead_timestamp <= last_seen:
                dropped_seen += 1
                continue
            new_signals.append(signal)

            # Register this market with the WS subscriber so future trades trigger fast polls
            cid = activity.get("conditionId") or activity.get("market_id") or ""
            token = activity.get("asset") or activity.get("tokenId") or ""
            if cid and token:
                ws.register(wallet_address, cid, token)

        # Always log so we can see what each poll returned
        log.info(
            "poll_result",
            wallet=wallet_address[:10],
            fetched=len(activities),
            dropped_normalize=dropped_normalize,
            dropped_seen=dropped_seen,
            new=len(new_signals),
            is_shadow=is_shadow,
        )

        # Log a sample raw activity on the first poll to diagnose field names
        if activities and wallet_address not in self._last_seen:
            sample = activities[0]
            log.info("poll_sample_activity", wallet=wallet_address[:10],
                     keys=list(sample.keys()), sample=str(sample)[:300])

        if new_signals:
            newest = max(s.lead_timestamp for s in new_signals)
            self._last_seen[wallet_address] = newest
            for signal in new_signals:
                await self._queue.put(signal)
            log.info(
                "new_signals_queued",
                wallet=wallet_address[:10],
                count=len(new_signals),
                is_shadow=is_shadow,
            )

    def stop(self) -> None:
        self._running = False
        get_clob_ws().stop()
        log.info("poller_stopped")
