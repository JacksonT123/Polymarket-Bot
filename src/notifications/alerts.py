"""Alert routing with 5-minute dedup."""
import asyncio
from datetime import timedelta
import structlog
from src.core.enums import NotificationSeverity
from src.core.clock import now
from src.notifications import discord, ntfy

log = structlog.get_logger(__name__)

_sent_at: dict[str, object] = {}  # key → datetime
_DEDUP_WINDOW = timedelta(minutes=5)


def _dedup_key(title: str, severity: NotificationSeverity) -> str:
    return f"{severity.value}:{title}"


def _is_recent(key: str) -> bool:
    sent = _sent_at.get(key)
    return sent is not None and (now() - sent) < _DEDUP_WINDOW


async def alert(
    title: str,
    body: str,
    severity: NotificationSeverity = NotificationSeverity.INFO,
    force: bool = False,
) -> None:
    """Route alert to Discord + ntfy with 5-minute dedup. Set force=True to bypass dedup."""
    key = _dedup_key(title, severity)
    if not force and _is_recent(key):
        log.debug("alert_deduped", title=title)
        return

    _sent_at[key] = now()
    message = f"**{title}**\n{body}"

    await asyncio.gather(
        discord.send(message, severity),
        ntfy.push(title, body, severity),
        return_exceptions=True,
    )
    log.info("alert_sent", title=title, severity=severity.value)
