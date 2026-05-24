"""Signal feed and history routes."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_session
from src.db.repositories import SignalRepo

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/recent")
async def recent_signals(
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
):
    signals = await SignalRepo(session).get_all_recent(limit=limit)
    return [
        {
            "id": s.id,
            "market_id": s.market_id,
            "side": s.side,
            "price": s.price,
            "value_usd": s.value_usd,
            "status": s.status,
            "is_shadow": s.is_shadow,
            "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        }
        for s in signals
    ]
