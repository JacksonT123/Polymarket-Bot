"""Paper mode uses the unified executor (same CLOB book path as live)."""
from __future__ import annotations

from bot.exec.executor import execute_copy
from bot.models import CopyIntent


async def execute_paper(intent: CopyIntent) -> dict | None:
    return await execute_copy(intent)
