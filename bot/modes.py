"""Mode enum and live-only guard. Mode is also exported from bot.models."""
from functools import wraps
from typing import Callable

from bot.models import Mode


def require_live(fn: Callable) -> Callable:
    """Decorator: raises if called in PAPER mode."""
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        mode = kwargs.get("mode") or (args[0] if args else None)
        if mode is Mode.PAPER:
            raise RuntimeError(f"{fn.__name__} cannot be called in PAPER mode")
        return await fn(*args, **kwargs)
    return wrapper
