"""ntfy.sh push notifications — no-op if NTFY_TOPIC not set."""
import aiohttp
import structlog
from src.core.enums import NotificationSeverity

log = structlog.get_logger(__name__)

NTFY_BASE = "https://ntfy.sh"

_priority_map = {
    NotificationSeverity.INFO:     "default",
    NotificationSeverity.WARN:  "high",
    NotificationSeverity.CRITICAL: "urgent",
}


async def push(title: str, body: str, severity: NotificationSeverity = NotificationSeverity.INFO) -> bool:
    """POST to ntfy.sh. Returns True on success, False if skipped/failed."""
    from config.secrets import get_secrets
    topic = get_secrets().ntfy_topic
    if not topic:
        return False

    headers = {
        "Title": title,
        "Priority": _priority_map.get(severity, "default"),
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{NTFY_BASE}/{topic}", data=body.encode(),
                headers=headers, timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                return resp.status == 200
    except Exception as e:
        log.error("ntfy_error", error=str(e))
        return False
