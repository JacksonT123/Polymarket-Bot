from __future__ import annotations

import asyncio
import time

from bot.config import get_settings
from bot.copy_planner.conflicts import ConflictTracker
from bot.copy_planner.planner import build_intent
from bot.data.client import DataAPIClient
from bot.data.coordinator import discovery_active, wait_until_not_discovering
from bot.engine import status as engine_status
from bot.exec.executor import execute_copy
from bot.leader_ranker.pipeline import get_active_leaders
from bot.ledger import repo
from bot.models import DecisionCode
from bot.observability.log import get_logger
from bot.risk_engine.caps import validate_intent

log = get_logger(__name__)


class CopyEngine:
    def __init__(self) -> None:
        self._client = DataAPIClient()
        self._conflicts = ConflictTracker()

    async def close(self) -> None:
        await self._client.close()

    async def process_leader(self, proxy: str) -> int:
        events = await self._client.get_recent_trade_events(proxy, limit=25)
        if not events:
            return 0

        last_ts = await repo.get_leader_cursor(proxy)
        if last_ts is None:
            newest = max(e.timestamp for e in events)
            await repo.set_leader_cursor(proxy, newest)
            log.info("leader_cursor_bootstrapped", proxy=proxy[:12], ts=newest)
            return 0

        new_events = [e for e in events if e.timestamp > last_ts]
        newest = max(e.timestamp for e in events)
        if newest > last_ts:
            await repo.set_leader_cursor(proxy, newest)

        for ev in new_events:
            t0 = time.time()
            if not await repo.mark_seen(ev.event_id):
                await repo.log_decision("detect", DecisionCode.SKIP_DUPLICATE, {}, ev)
                continue

            await repo.log_decision(
                "detect",
                "DETECTED",
                {"latency_ms": int((time.time() - t0) * 1000), "source": "activity_api"},
                ev,
            )

            intent, plan_skip, sizing = await build_intent(self._client, ev)
            if plan_skip or intent is None:
                await repo.log_decision("plan", plan_skip or DecisionCode.SKIP_PARSE_ERROR, sizing, ev)
                continue

            conflict = self._conflicts.check(intent)
            if conflict:
                await repo.log_decision("conflict", conflict, {"sizing": sizing}, ev)
                continue

            state = await repo.get_account_state()
            cash = float(state.get("cash_usd") or 0)
            equity = float(state.get("equity_usd") or 0)
            risk = await validate_intent(intent, cash, equity)
            if risk:
                await repo.log_decision("risk", risk, {"cash": cash, "target": intent.target_notional}, ev)
                continue

            fill = await execute_copy(intent)
            if fill is None:
                await repo.log_decision("execute", DecisionCode.SKIP_EXECUTION_ERROR, {}, ev)
                continue
            if fill.get("status") != "filled":
                await repo.log_decision(
                    "execute",
                    fill.get("code", DecisionCode.SKIP_MARKET_ILLQUID),
                    fill,
                    ev,
                )
                continue

            engine_status.record_copy()
            await repo.log_decision(
                "execute",
                DecisionCode.COPIED,
                {**fill, "plan_ms": int((time.time() - t0) * 1000)},
                ev,
            )
            log.info("copied_trade", leader=ev.leader_proxy, side=ev.side, mode=fill.get("mode"))

        return len(new_events)

    async def run_once(self) -> None:
        if discovery_active():
            await wait_until_not_discovering()
            return

        leaders = await get_active_leaders(self._client)
        if not leaders:
            engine_status.record_poll(leaders=0, events=0)
            return

        total_events = 0
        for l in leaders:
            if discovery_active():
                break
            try:
                n = await self.process_leader(l.proxy)
                total_events += n
            except Exception as e:
                engine_status.record_api_error(str(e))
                log.error("leader_process_error", proxy=l.proxy[:12], error=str(e))

        engine_status.record_poll(leaders=len(leaders), events=total_events)

    async def run_loop(self, stop: asyncio.Event) -> None:
        cfg = get_settings()
        while not stop.is_set():
            try:
                await self.run_once()
            except Exception as e:
                engine_status.record_api_error(str(e))
                log.error("engine_loop_error", error=str(e))
            try:
                await asyncio.wait_for(stop.wait(), timeout=cfg.activity_poll_seconds)
            except asyncio.TimeoutError:
                pass
