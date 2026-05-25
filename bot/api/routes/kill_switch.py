"""GET/POST /api/kill-switch — manual trigger and reset."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from bot.ledger import repo
from bot.observability.log import get_logger

log = get_logger(__name__)
router = APIRouter()


class KillSwitchAction(BaseModel):
    action: str  # "trigger" or "reset"
    reason: str = "manual"


@router.get("")
async def get_kill_switch() -> dict:
    raw = await repo.get_kill_switch()
    return {
        "active": raw.get("triggered", False),
        "triggered_at": raw.get("triggered_at"),
        "reason": raw.get("reason"),
        "daily_loss_usd": raw.get("daily_loss_usd"),
    }


@router.post("")
async def set_kill_switch(body: KillSwitchAction) -> dict:
    if body.action == "trigger":
        await repo.trigger_kill_switch(reason=body.reason)
        log.warning("kill_switch_manual_trigger", reason=body.reason)
    elif body.action == "reset":
        await repo.reset_kill_switch()
        log.info("kill_switch_manual_reset")
    else:
        raise HTTPException(status_code=400, detail="action must be 'trigger' or 'reset'")
    raw = await repo.get_kill_switch()
    return {
        "active": raw.get("triggered", False),
        "triggered_at": raw.get("triggered_at"),
        "reason": raw.get("reason"),
        "daily_loss_usd": raw.get("daily_loss_usd"),
    }
