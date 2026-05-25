"""GET/POST /api/settings — runtime-adjustable bot parameters."""
from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from bot.ledger import repo

router = APIRouter()

_ALLOWED_KEYS = {
    "mode",
    "base_trade_usd",
    "max_position_pct",
    "kill_switch_daily_loss_usd",
    "aggregation_window_secs",
    "max_position_age_hours",
    "stop_loss_enabled",
    "roster_active_size",
    "roster_standby_size",
}

_DEFAULTS: dict[str, Any] = {
    "mode": "PAPER",
    "base_trade_usd": 5.0,
    "max_position_pct": 0.10,
    "kill_switch_daily_loss_usd": 40.0,
    "aggregation_window_secs": 120,
    "max_position_age_hours": 168,
    "stop_loss_enabled": False,
    "roster_active_size": 30,
    "roster_standby_size": 20,
}


class SettingsUpdate(BaseModel):
    mode: Optional[str] = None
    base_trade_usd: Optional[float] = None
    max_position_pct: Optional[float] = None
    kill_switch_daily_loss_usd: Optional[float] = None
    aggregation_window_secs: Optional[int] = None
    max_position_age_hours: Optional[int] = None
    stop_loss_enabled: Optional[bool] = None
    roster_active_size: Optional[int] = None
    roster_standby_size: Optional[int] = None


def _cast(key: str, raw: str) -> Any:
    default = _DEFAULTS.get(key)
    if isinstance(default, bool):
        return raw.lower() in ("true", "1", "yes")
    if isinstance(default, int):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    return raw


@router.get("")
async def get_settings() -> dict:
    raw = await repo.get_all_settings()
    result = dict(_DEFAULTS)
    for k, v in raw.items():
        if k in _DEFAULTS:
            result[k] = _cast(k, v)
    return result


@router.post("")
async def update_settings(body: SettingsUpdate) -> dict:
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        if key not in _ALLOWED_KEYS:
            raise HTTPException(status_code=400, detail=f"Key '{key}' is not adjustable at runtime")
        await repo.set_setting(key, str(value))
    return await get_settings()
