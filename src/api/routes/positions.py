"""Position list and management routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.api.deps import get_session
from src.db.repositories import PositionRepo
from src.db.models import Position as PositionModel

router = APIRouter(prefix="/positions", tags=["positions"])


def _pos_dict(p) -> dict:
    return {
        "id": p.id,
        "market_id": p.market_id,
        "token_id": p.token_id,
        "side": p.side,
        "entry_price": p.entry_price,
        "current_price": p.current_price,
        "size_shares": p.size_shares,
        "cost_usd": p.cost_usd,
        "unrealized_pnl_usd": p.unrealized_pnl_usd,
        "realized_pnl_usd": p.realized_pnl_usd,
        "status": p.status,
        "is_shadow": p.is_shadow,
        "opened_at": p.opened_at.isoformat() if p.opened_at else None,
        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
        "exit_reason": p.exit_reason,
    }


@router.get("/open")
async def list_open(session: AsyncSession = Depends(get_session)):
    ps = await PositionRepo(session).get_open(is_shadow=False)
    return [_pos_dict(p) for p in ps]


@router.get("/open/shadow")
async def list_open_shadow(session: AsyncSession = Depends(get_session)):
    ps = await PositionRepo(session).get_open(is_shadow=True)
    return [_pos_dict(p) for p in ps]


@router.get("/{position_id}")
async def get_position(position_id: int, session: AsyncSession = Depends(get_session)):
    p = await session.scalar(select(PositionModel).where(PositionModel.id == position_id))
    if not p:
        raise HTTPException(404, "Position not found")
    return _pos_dict(p)


@router.post("/{position_id}/exit")
async def force_exit(position_id: int, session: AsyncSession = Depends(get_session)):
    from src.execution.order_engine import OrderEngine
    from src.positions.exiter import ExitHandler
    from src.db.engine import get_session_factory
    p = await session.scalar(select(PositionModel).where(PositionModel.id == position_id))
    if not p:
        raise HTTPException(404, "Position not found")
    engine = OrderEngine()
    handler = ExitHandler(engine, get_session_factory())
    await handler.on_manual(p)
    return {"ok": True}
