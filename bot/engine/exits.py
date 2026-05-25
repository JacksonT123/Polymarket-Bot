"""
Exit triggers — monitors open positions and emits sell signals when any
of the 4 exit conditions are met:
  1. Leader closes position (mirror exit)
  2. Market resolves (resolution exit)
  3. Position value drops 50% from entry (stop-loss — disabled by default per spec)
  4. Position age > 7 days (time-based exit)
"""
from __future__ import annotations

import asyncio
import time
from typing import Callable

from bot.config import get_settings
from bot.data.data_api import DataAPIClient
from bot.ledger import repo
from bot.models import OrderSide, SignalEvent, SignalStatus
from bot.observability.log import get_logger

log = get_logger(__name__)

_CHECK_INTERVAL = 30  # seconds between exit scans
_MAX_POSITION_AGE_HOURS = 168  # 7 days


class ExitMonitor:
    """
    Periodically scans open positions against exit conditions.
    Emits a synthetic SignalEvent(side=SELL) when an exit is triggered.
    """

    def __init__(
        self,
        client: DataAPIClient,
        on_exit_signal: Callable[[SignalEvent], None],
        mode: str = "PAPER",
    ) -> None:
        self._client = client
        self._on_exit_signal = on_exit_signal
        self._mode = mode
        self._running = False
        # Track which leader positions have already been detected as closed
        # to avoid re-emitting: condition_id → set of leader proxies
        self._leader_close_seen: dict[str, set[str]] = {}

    async def run(self) -> None:
        self._running = True
        log.info("exit_monitor_start", mode=self._mode)
        while self._running:
            try:
                await self._scan()
            except Exception as e:
                log.error("exit_monitor_error", error=str(e))
            await asyncio.sleep(_CHECK_INTERVAL)

    def stop(self) -> None:
        self._running = False

    async def _scan(self) -> None:
        positions = await repo.get_open_positions(self._mode)
        if not positions:
            return

        leaders = await repo.get_active_leaders()
        leader_map = {l.proxy_address: l for l in leaders}

        for pos in positions:
            condition_id = pos["condition_id"]
            token_id = pos["token_id"]

            # Exit 1: Mirror exit — leader closed their position
            await self._check_leader_exit(pos, leader_map, condition_id, token_id)

            # Exit 2: Market resolved
            await self._check_resolution(pos, condition_id, token_id)

            # Exit 3: Stop-loss (disabled per spec — monitored only)
            cfg = get_settings()
            if cfg.stop_loss_enabled:
                self._check_stop_loss(pos, condition_id, token_id)

            # Exit 4: Time-based exit
            self._check_age_exit(pos, condition_id, token_id)

    async def _check_leader_exit(self, pos, leader_map, condition_id, token_id) -> None:
        """If the leader who triggered this position has no open position → exit."""
        leader_ranks: list[int] = pos.get("leader_ranks", [])
        leader_proxies = [l.proxy_address for l in leader_map.values() if l.rank in leader_ranks]

        for proxy in leader_proxies:
            seen = self._leader_close_seen.setdefault(condition_id, set())
            if proxy in seen:
                continue

            try:
                positions = await self._client.get_positions(user=proxy, limit=50, sort_by="CURRENT")
                open_markets = {p.get("conditionId", "") for p in positions if p.get("size", 0) > 0}
                if condition_id not in open_markets:
                    seen.add(proxy)
                    log.info(
                        "exit_leader_close",
                        condition_id=condition_id[:12],
                        proxy=proxy[:12],
                    )
                    self._emit_exit(pos, condition_id, token_id, "leader_exit")
                    return
            except Exception as e:
                log.warning("exit_leader_check_error", error=str(e))

    async def _check_resolution(self, pos, condition_id, token_id) -> None:
        """If market is resolved, exit."""
        try:
            from bot.data.gamma import GammaClient
            async with GammaClient() as gamma:
                market = await gamma.get_market(condition_id)
                if market and market.get("closed"):
                    log.info("exit_market_resolved", condition_id=condition_id[:12])
                    self._emit_exit(pos, condition_id, token_id, "market_resolved")
        except Exception as e:
            log.warning("exit_resolution_check_error", error=str(e))

    def _check_stop_loss(self, pos, condition_id, token_id) -> None:
        """Emit exit if current value < 50% of cost."""
        cost = pos.get("cost_usd", 0)
        current_value = pos.get("current_value_usd", cost)
        if cost > 0 and current_value < cost * 0.50:
            log.warning("exit_stop_loss", condition_id=condition_id[:12], loss_pct=1 - current_value / cost)
            self._emit_exit(pos, condition_id, token_id, "stop_loss")

    def _check_age_exit(self, pos, condition_id, token_id) -> None:
        """Emit exit if position is older than 7 days."""
        opened_at = pos.get("opened_at_ts", time.time())
        age_hours = (time.time() - opened_at) / 3600
        if age_hours > _MAX_POSITION_AGE_HOURS:
            log.info("exit_age", condition_id=condition_id[:12], age_hours=age_hours)
            self._emit_exit(pos, condition_id, token_id, "age_exit")

    def _emit_exit(self, pos, condition_id, token_id, reason: str) -> None:
        signal = SignalEvent(
            proxy_address="exit_monitor",
            leader_rank=pos.get("leader_ranks", [99])[0] if pos.get("leader_ranks") else 99,
            condition_id=condition_id,
            token_id=token_id,
            outcome=pos.get("outcome", ""),
            side=OrderSide.SELL,
            leader_price=pos.get("current_price", pos.get("avg_entry_price", 0.5)),
            leader_size=pos.get("shares", 0),
            detected_ts=int(time.time()),
            status=SignalStatus.PENDING,
            exit_reason=reason,
        )
        self._on_exit_signal(signal)
