"""Async event queues for live and shadow signals."""
import asyncio
from src.core.models import SignalEvent


class SignalQueue:
    """Separate queues for live vs shadow signals."""
    def __init__(self, maxsize: int = 1000):
        self.live: asyncio.Queue[SignalEvent] = asyncio.Queue(maxsize=maxsize)
        self.shadow: asyncio.Queue[SignalEvent] = asyncio.Queue(maxsize=maxsize)

    async def put(self, signal: SignalEvent) -> None:
        queue = self.shadow if signal.is_shadow else self.live
        try:
            queue.put_nowait(signal)
        except asyncio.QueueFull:
            # Drop and log — don't block the poller
            import structlog
            structlog.get_logger().warning("signal_queue_full", is_shadow=signal.is_shadow)

    def qsize(self) -> dict[str, int]:
        return {"live": self.live.qsize(), "shadow": self.shadow.qsize()}


_signal_queue: SignalQueue | None = None


def get_signal_queue() -> SignalQueue:
    global _signal_queue
    if _signal_queue is None:
        _signal_queue = SignalQueue()
    return _signal_queue
