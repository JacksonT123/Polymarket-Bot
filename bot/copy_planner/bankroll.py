from __future__ import annotations

import time

from bot.config import get_settings
from bot.data.client import DataAPIClient
from bot.ledger import repo
from bot.models import BankrollSnapshot


async def get_leader_bankroll(client: DataAPIClient, proxy: str) -> BankrollSnapshot:
    cfg = get_settings()
    cached = await repo.get_cached_bankroll(proxy, cfg.bankroll_cache_seconds)
    now = int(time.time())
    if cached is not None and cached > 0:
        return BankrollSnapshot(proxy=proxy, bankroll_usd=cached, updated_at=now, stale=False)

    bankroll = await client.estimate_bankroll_usd(proxy)
    if bankroll > 0:
        await repo.set_cached_bankroll(proxy, bankroll)
    stale = bankroll <= 0
    return BankrollSnapshot(proxy=proxy, bankroll_usd=bankroll, updated_at=now, stale=stale)


async def get_my_bankroll() -> float:
    state = await repo.get_account_state()
    return max(float(state.get("equity_usd") or 0), float(state.get("cash_usd") or 0))
