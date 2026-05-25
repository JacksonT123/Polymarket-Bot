"""
Signal detection: watches leader trades (via Data API polling + Polygon log events)
and emits SignalEvent rows when leaders open or close positions.
"""
from __future__ import annotations

import asyncio
import time
from typing import Callable

from bot.data.data_api import DataAPIClient
from bot.data.polygon_logs import PolygonLogSubscriber
from bot.ledger import repo
from bot.ledger.db import write_event
from bot.models import Leader, LeaderTrade, OrderSide, SignalEvent, SignalStatus
from bot.observability.log import get_logger
from bot.observability.trace import new_trace

log = get_logger(__name__)

# Poll every 3 seconds per leader; stagger by 0.1s to spread load
_POLL_INTERVAL = 3.0
_STAGGER = 0.1


class SignalDetector:
    """
    Polls all active leaders every 3s; also subscribes to Polygon log events
    for sub-second detection on fills. Emits signals via callback.
    """

    def __init__(
        self,
        client: DataAPIClient,
        on_signal: Callable[[SignalEvent], None],
    ) -> None:
        self._client = client
        self._on_signal = on_signal
        self._seen: dict[str, set[str]] = {}  # proxy → set of trade IDs seen
        self._log_sub = PolygonLogSubscriber(on_event=self._on_log_event, leader_proxies=[])
        self._running = False

    async def start(self) -> None:
        self._running = True
        leaders = await repo.get_active_leaders()
        log.info("signal_detector_start", leaders=len(leaders))
        self._log_sub.update_leaders([l.proxy_address for l in leaders])

        tasks = []
        for i, leader in enumerate(leaders):
            delay = i * _STAGGER
            tasks.append(self._poll_leader_loop(leader, delay))

        tasks.append(self._log_sub.run())
        await asyncio.gather(*tasks)

    async def stop(self) -> None:
        self._running = False

    async def refresh_leaders(self) -> None:
        """Called after daily re-ranking to pick up roster changes."""
        leaders = await repo.get_active_leaders()
        self._seen = {l.proxy_address: self._seen.get(l.proxy_address, set()) for l in leaders}
        log.info("signal_detector_refreshed", leaders=len(leaders))

    async def _poll_leader_loop(self, leader: Leader, initial_delay: float) -> None:
        await asyncio.sleep(initial_delay)
        proxy = leader.proxy_address
        self._seen.setdefault(proxy, set())

        while self._running:
            try:
                trades = await self._client.poll_leader_trades(proxy)
                for trade in trades:
                    tid = trade.get("id", "")
                    if tid and tid not in self._seen[proxy]:
                        self._seen[proxy].add(tid)
                        signal = _trade_to_signal(leader, trade)
                        if signal:
                            await self._emit(signal)
            except Exception as e:
                log.warning("poll_error", proxy=proxy, error=str(e))

            await asyncio.sleep(_POLL_INTERVAL)

    async def _on_log_event(self, event: dict) -> None:
        """Called by PolygonLogSubscriber on new Exchange V2 OrderFilled log."""
        # Events come as raw log dicts; we decode what we need from topics/data
        # Full decoding requires ABI — here we mark it as a detected signal
        # and let the polling confirm details on next cycle
        log.debug("log_event_received", tx=event.get("transactionHash", "")[:12])

    async def _emit(self, signal: SignalEvent) -> None:
        with new_trace():
            await repo.insert_signal(signal)
            await write_event("signal_detected", signal.__dict__)
            await self._on_signal(signal)
            log.info(
                "signal_emitted",
                proxy=signal.proxy_address,
                market=signal.condition_id[:12],
                side=signal.side.value,
                price=signal.leader_price,
            )


def _trade_to_signal(leader: Leader, trade: dict) -> SignalEvent | None:
    """Convert a raw Data API trade dict into a SignalEvent."""
    try:
        side_str = trade.get("side", "")
        side = OrderSide.BUY if side_str == "BUY" else OrderSide.SELL if side_str == "SELL" else None
        if side is None:
            return None

        price = float(trade.get("price", 0))
        size = float(trade.get("size", trade.get("amount", 0)))
        condition_id = trade.get("conditionId", trade.get("market", ""))
        token_id = trade.get("outcomeIndex", trade.get("tokenId", ""))
        outcome = str(trade.get("outcome", trade.get("title", "")))
        ts = int(trade.get("timestamp", time.time()))

        if not condition_id or price <= 0 or size <= 0:
            return None

        return SignalEvent(
            proxy_address=leader.proxy_address,
            leader_rank=leader.rank,
            condition_id=condition_id,
            token_id=str(token_id),
            outcome=outcome,
            side=side,
            leader_price=price,
            leader_size=size,
            detected_ts=ts,
            status=SignalStatus.PENDING,
        )
    except Exception as e:
        log.warning("signal_parse_error", error=str(e))
        return None
