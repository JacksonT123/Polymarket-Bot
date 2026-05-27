#!/usr/bin/env python3
"""Run bot components and report API health for ~2 minutes."""
import asyncio
import json
import sys
import time
import urllib.request

from bot.config import get_settings
from bot.data import rate_limit
from bot.engine import status as engine_status
from bot.engine.runner import CopyEngine
from bot.ledger.db import init_db
from bot.leader_ranker.pipeline import run_discovery
from bot.ledger import repo


async def main() -> int:
    await init_db()
    rate_limit.reset_stats()

    cfg = get_settings()
    leaders = await repo.get_leaders(status="active")
    if not leaders:
        print("Running discovery...")
        await run_discovery()
        leaders = await repo.get_leaders(status="active")
    print(f"Active leaders: {len(leaders)}")

    engine = CopyEngine()
    stop = asyncio.Event()
    task = asyncio.create_task(engine.run_loop(stop))
    t0 = time.time()
    duration = 120
    samples = []

    while time.time() - t0 < duration:
        await asyncio.sleep(10)
        snap = engine_status.snapshot()
        samples.append(snap)
        print(
            f"  t+{int(time.time()-t0)}s polls={snap['poll_cycles']} "
            f"rate_hits={snap['rate_limit_hits']} api_err={snap['api_errors']} "
            f"cooldown={snap['rate_limit_cooldown_sec']}s"
        )

    stop.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await engine.close()

    final = engine_status.snapshot()
    ok = final["rate_limit_hits"] <= 3 and final["api_errors"] <= 5
    print("\n=== RESULT ===")
    print(json.dumps(final, indent=2))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
