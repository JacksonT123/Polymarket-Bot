"""Discord webhook notifications — stubs to console if webhook URL not set."""
import aiohttp
import structlog
from src.core.enums import NotificationSeverity

log = structlog.get_logger(__name__)


async def send(message: str, severity: NotificationSeverity = NotificationSeverity.INFO) -> bool:
    """POST to Discord webhook. Returns True on success, False if skipped/failed."""
    from config.secrets import get_secrets
    url = get_secrets().discord_webhook_url
    if not url:
        log.info("discord_no_webhook", severity=severity.value, message=message[:80])
        return False

    color_map = {
        NotificationSeverity.INFO:     0x3498DB,
        NotificationSeverity.WARN:  0xF39C12,
        NotificationSeverity.CRITICAL: 0xE74C3C,
    }
    payload = {
        "embeds": [{
            "description": message,
            "color": color_map.get(severity, 0x95A5A6),
        }]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status in (200, 204):
                    return True
                log.warning("discord_send_failed", status=resp.status)
                return False
    except Exception as e:
        log.error("discord_error", error=str(e))
        return False
