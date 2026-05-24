"""Config read/write and control routes."""
from fastapi import APIRouter
from src.risk import killswitch

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/")
async def get_config():
    import config.settings as s
    from config.secrets import get_secrets
    sec = get_secrets()
    return {
        "trading_mode": sec.trading_mode,
        "killswitch_active": sec.killswitch_active,
        "tier_override": sec.tier_override,
        "dashboard_port": sec.dashboard_port,
    }


@router.get("/circuit-breakers")
async def circuit_breaker_status():
    from src.risk.circuit_breakers import CircuitBreakerManager
    return {"note": "CircuitBreakerManager state lives in the runner process; check logs for current status."}


@router.post("/webhook-test")
async def test_webhook():
    from src.notifications.alerts import alert
    from src.core.enums import NotificationSeverity
    await alert("Webhook Test", "Test message from Polymarket Copy Bot dashboard.", NotificationSeverity.INFO, force=True)
    return {"ok": True}
