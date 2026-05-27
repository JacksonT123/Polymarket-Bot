from __future__ import annotations

from typing import Protocol

from bot.models import CopyIntent


class Executor(Protocol):
    async def execute(self, intent: CopyIntent) -> dict | None: ...
