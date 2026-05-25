"""
Print the current leader roster to stdout.
Run: `uv run python -m bot.scripts.dump_roster`
"""
from __future__ import annotations

import asyncio

from bot.ledger import repo
from bot.ledger.db import init_db
from bot.observability.log import configure_logging


async def main() -> None:
    configure_logging()
    await init_db()
    leaders = await repo.get_roster()

    if not leaders:
        print("No roster found. Run the discovery job first.")
        return

    print(f"\n{'Rank':<6} {'Tier':<10} {'Score':<10} {'Delta':<10} {'Proxy'}")
    print("-" * 72)
    for l in leaders:
        delta_str = f"{l.score_delta:+.4f}" if l.score_delta else "  n/a"
        print(f"{l.rank:<6} {l.tier.value:<10} {l.score:<10.4f} {delta_str:<10} {l.proxy_address}")

    print(f"\nTotal: {len(leaders)} leaders | Date: {leaders[0].snapshot_date if leaders else 'n/a'}")


if __name__ == "__main__":
    asyncio.run(main())
