import asyncio

from bot.data.client import DataAPIClient
from bot.ledger.db import init_db
from bot.leader_ranker.pipeline import run_discovery


async def main() -> None:
    await init_db()
    client = DataAPIClient()
    proxies = await client.get_all_leaderboard_candidates(30)
    print("proxies", len(proxies), proxies[:3])
    await client.close()
    leaders = await run_discovery()
    print("leaders", len(leaders))
    for l in leaders[:5]:
        print(l.rank, l.proxy[:16], f"score={l.score:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
