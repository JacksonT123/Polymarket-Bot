"""Funnel pipeline state routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_session
from src.db.repositories import WalletRepo
from src.core.enums import WalletStatus

router = APIRouter(prefix="/funnel", tags=["funnel"])


@router.get("/counts")
async def funnel_counts(session: AsyncSession = Depends(get_session)):
    repo = WalletRepo(session)
    counts = {}
    for s in WalletStatus:
        ws = await repo.get_by_status(s)
        counts[s.value] = len(ws)
    return counts


@router.get("/shadow")
async def shadow_wallets(session: AsyncSession = Depends(get_session)):
    ws = await WalletRepo(session).get_by_status(WalletStatus.SHADOW)
    return [
        {
            "address": w.address,
            "composite_score": w.composite_score,
            "shadow_pnl_usd": w.shadow_pnl_usd,
            "shadow_capture_ratio": w.shadow_capture_ratio,
            "shadow_copies_count": w.shadow_copies_count,
            "shadow_started_at": w.shadow_started_at.isoformat() if w.shadow_started_at else None,
        }
        for w in ws
    ]


@router.post("/run")
async def trigger_funnel():
    """Trigger a funnel re-run (async, returns immediately)."""
    import asyncio
    from src.funnel.orchestrator import run_funnel_pipeline
    from src.db.engine import get_session_factory
    asyncio.create_task(run_funnel_pipeline(get_session_factory()))
    return {"ok": True, "message": "Funnel re-run triggered"}
