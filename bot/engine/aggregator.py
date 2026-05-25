"""
120-second aggregation window: buffers signals for the same market/side,
then flushes as a single combined OrderIntent with averaged price and summed size.
Multiple leaders in the same market within 120s → one order.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Callable

from bot.models import OrderIntent, OrderSide, SignalEvent
from bot.observability.log import get_logger

log = get_logger(__name__)

_WINDOW_SECONDS = 120


class _Bucket:
    def __init__(self) -> None:
        self.signals: list[SignalEvent] = []
        self.created_at: float = time.time()

    def add(self, signal: SignalEvent) -> None:
        self.signals.append(signal)

    def is_expired(self) -> bool:
        return time.time() - self.created_at >= _WINDOW_SECONDS

    def flush(self) -> list[SignalEvent]:
        s = list(self.signals)
        self.signals.clear()
        return s


class SignalAggregator:
    """
    Buffers incoming signals by (condition_id, outcome, side) for 120s,
    then calls on_flush with the combined list for sizing + execution.
    """

    def __init__(self, on_flush: Callable[[list[SignalEvent]], None]) -> None:
        self._on_flush = on_flush
        # key: (condition_id, outcome, side) → bucket
        self._buckets: dict[tuple, _Bucket] = defaultdict(_Bucket)
        self._lock = asyncio.Lock()
        self._running = False

    def ingest(self, signal: SignalEvent) -> None:
        """Thread-safe ingestion — can be called from any coroutine."""
        key = (signal.condition_id, signal.outcome, signal.side)
        if key not in self._buckets:
            self._buckets[key] = _Bucket()
            log.debug("aggregator_new_bucket", market=signal.condition_id[:12], side=signal.side.value)
        self._buckets[key].add(signal)
        log.debug(
            "aggregator_signal_buffered",
            market=signal.condition_id[:12],
            buffered=len(self._buckets[key].signals),
        )

    async def run(self) -> None:
        """Background task: check buckets every second, flush expired ones."""
        self._running = True
        while self._running:
            await asyncio.sleep(1.0)
            expired_keys = [k for k, b in self._buckets.items() if b.is_expired()]
            for key in expired_keys:
                bucket = self._buckets.pop(key)
                signals = bucket.flush()
                if signals:
                    log.info(
                        "aggregator_flush",
                        market=key[0][:12],
                        side=key[2].value,
                        count=len(signals),
                    )
                    try:
                        self._on_flush(signals)
                    except Exception as e:
                        log.error("aggregator_flush_error", error=str(e))

    def stop(self) -> None:
        self._running = False
        # Flush remaining
        for key, bucket in list(self._buckets.items()):
            signals = bucket.flush()
            if signals:
                try:
                    self._on_flush(signals)
                except Exception:
                    pass
        self._buckets.clear()
