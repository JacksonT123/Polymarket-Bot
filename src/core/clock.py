from datetime import datetime, timezone
from typing import Callable

_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)


def now() -> datetime:
    """UTC now. Use this everywhere — never datetime.now() directly."""
    return _clock()


def set_clock(fn: Callable[[], datetime]) -> None:
    """Override the clock for tests."""
    global _clock
    _clock = fn


def reset_clock() -> None:
    global _clock
    _clock = lambda: datetime.now(timezone.utc)
