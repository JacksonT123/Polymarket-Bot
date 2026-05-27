import asyncio

from bot.ledger.db import init_db
from bot.leader_ranker.pipeline import run_discovery


async def main() -> None:
    await init_db()
    leaders = await run_discovery()
    print("active", len(leaders))
    if leaders:
        print("top", leaders[0].proxy[:16], leaders[0].score)


if __name__ == "__main__":
    asyncio.run(main())
