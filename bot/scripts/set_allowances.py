"""
Approve pUSD for CLOB Exchange V2 at MAX_UINT256.
Run once before going live: `uv run python -m bot.scripts.set_allowances`
"""
from __future__ import annotations

import asyncio

from bot.observability.log import configure_logging, get_logger
from bot.security.allowances import set_allowances

log = get_logger(__name__)


async def main() -> None:
    configure_logging()
    log.info("set_allowances_start")
    await set_allowances()
    log.info("set_allowances_done")


if __name__ == "__main__":
    asyncio.run(main())
