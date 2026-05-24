"""Health check and Prometheus metrics endpoints."""
from fastapi import APIRouter
from src.core.clock import now

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "ts": now().isoformat()}


@router.get("/metrics")
async def metrics():
    from src.execution.queue import get_signal_queue
    from src.risk import killswitch
    q = get_signal_queue()
    return {
        "queue_live": q.qsize()["live"],
        "queue_shadow": q.qsize()["shadow"],
        "killswitch_active": killswitch.is_active(),
    }
