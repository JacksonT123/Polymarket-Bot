"""Wallet list and management routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_session
from src.db.repositories import WalletRepo
from src.core.enums import WalletStatus

router = APIRouter(prefix="/wallets", tags=["wallets"])


def _wallet_dict(w) -> dict:
    return {
        "address": w.address,
        "status": w.status,
        "composite_score": w.composite_score,
        "win_rate": w.win_rate,
        "profit_factor": w.profit_factor,
        "primary_category": w.primary_category,
        "shadow_capture_ratio": w.shadow_capture_ratio,
        "recent_capture_ratio": w.recent_capture_ratio,
        "consecutive_losses_for_bot": w.consecutive_losses_for_bot,
        "closed_trades_count": w.closed_trades_count,
        "activated_at": w.activated_at.isoformat() if w.activated_at else None,
    }


@router.get("/")
async def list_wallets(
    status: str = Query("active"),
    session: AsyncSession = Depends(get_session),
):
    try:
        ws = await WalletRepo(session).get_by_status(WalletStatus(status))
    except ValueError:
        raise HTTPException(400, f"Unknown status: {status}")
    return [_wallet_dict(w) for w in ws]


@router.get("/{address}")
async def get_wallet(address: str, session: AsyncSession = Depends(get_session)):
    w = await WalletRepo(session).get_by_address(address)
    if not w:
        raise HTTPException(404, "Wallet not found")
    return _wallet_dict(w)


@router.post("/{address}/suspend")
async def suspend_wallet(address: str, session: AsyncSession = Depends(get_session)):
    repo = WalletRepo(session)
    w = await repo.get_by_address(address)
    if not w:
        raise HTTPException(404, "Wallet not found")
    await repo.update_status(address, WalletStatus.SUSPENDED)
    await session.commit()
    return {"ok": True}


@router.post("/{address}/promote")
async def promote_wallet(address: str, session: AsyncSession = Depends(get_session)):
    repo = WalletRepo(session)
    w = await repo.get_by_address(address)
    if not w:
        raise HTTPException(404, "Wallet not found")
    await repo.update_status(address, WalletStatus.ACTIVE)
    await session.commit()
    return {"ok": True}
