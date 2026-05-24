"""Equity snapshot routes."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_session
from src.db.repositories import EquityRepo

router = APIRouter(prefix="/equity", tags=["equity"])


@router.get("/latest")
async def equity_latest(session: AsyncSession = Depends(get_session)):
    snap = await EquityRepo(session).get_last()
    if not snap:
        return {"total_equity": 0.0, "cash_balance": 0.0, "position_value": 0.0}
    return {
        "total_equity": snap.total_equity,
        "cash_balance": snap.cash_balance,
        "position_value": snap.position_value,
        "open_position_count": snap.open_position_count,
        "daily_pnl": snap.daily_pnl,
        "weekly_pnl": snap.weekly_pnl,
        "all_time_pnl": snap.all_time_pnl,
        "ts": snap.timestamp.isoformat() if snap.timestamp else None,
    }


@router.get("/history")
async def equity_history(
    window: str = Query("7d", description="1d | 7d | 30d | all"),
    session: AsyncSession = Depends(get_session),
):
    from datetime import timedelta
    from src.core.clock import now
    windows = {"1d": timedelta(days=1), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    delta = windows.get(window)
    since = (now() - delta) if delta else None
    repo = EquityRepo(session)
    if since:
        snaps = await repo.get_range(since)
    else:
        from datetime import timedelta
        snaps = await repo.get_range(now() - timedelta(days=365 * 10))
    return [
        {"ts": s.timestamp.isoformat(), "total_equity": s.total_equity}
        for s in snaps
    ]
