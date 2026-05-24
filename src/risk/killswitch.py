"""Killswitch — halts new orders within 30s when KILLSWITCH env var is set."""
import asyncio
import structlog
from config.secrets import get_secrets
from src.core.exceptions import KillswitchError

log = structlog.get_logger(__name__)

_active = False
_monitor_task: asyncio.Task | None = None


def is_active() -> bool:
    return _active


def check_and_raise() -> None:
    """Call before every new order. Raises KillswitchError if killswitch is active."""
    if _active:
        raise KillswitchError("killswitch_active")


async def _monitor_loop(poll_interval_s: float = 15.0) -> None:
    global _active
    while True:
        try:
            secrets = get_secrets()
            currently_set = secrets.killswitch_active
            if currently_set and not _active:
                _active = True
                log.critical("killswitch_engaged")
            elif not currently_set and _active:
                _active = False
                log.warning("killswitch_cleared")
        except Exception as e:
            log.error("killswitch_monitor_error", error=str(e))
        await asyncio.sleep(poll_interval_s)


def start_monitor() -> None:
    global _monitor_task
    if _monitor_task is None or _monitor_task.done():
        _monitor_task = asyncio.create_task(_monitor_loop())
        log.info("killswitch_monitor_started")


def stop_monitor() -> None:
    global _monitor_task
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()
        _monitor_task = None
