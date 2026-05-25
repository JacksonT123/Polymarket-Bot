"""
Router: receives flushed signal batches from the aggregator,
resolves conflicts, computes size, builds OrderIntent, dispatches to executor.
"""
from __future__ import annotations

import asyncio
import time
from typing import Callable

from bot.clob.orders import build_order_intent, compute_fok_price
from bot.clob.ws_market import get_book
from bot.engine.conflicts import resolve_conflicts
from bot.engine.sizer import aggregate_signals_size
from bot.ledger import repo
from bot.models import OrderIntent, OrderSide, SignalEvent
from bot.observability.log import get_logger
from bot.observability.metrics import get_topline
from bot.observability.trace import new_span

log = get_logger(__name__)


class OrderRouter:
    """
    Sits between the aggregator and executor.
    Validates market conditions, resolves conflicts, sizes the order,
    and enqueues an OrderIntent for the executor.
    """

    def __init__(
        self,
        on_intent: Callable[[OrderIntent], None],
        mode: str = "PAPER",
    ) -> None:
        self._on_intent = on_intent
        self._mode = mode
        self._queue: asyncio.Queue[list[SignalEvent]] = asyncio.Queue()

    def enqueue(self, signals: list[SignalEvent]) -> None:
        """Called by aggregator.on_flush — non-blocking."""
        self._queue.put_nowait(signals)

    async def run(self) -> None:
        """Process batches from the queue serially."""
        while True:
            signals = await self._queue.get()
            try:
                await self._process(signals)
            except Exception as e:
                log.error("router_process_error", error=str(e))
            finally:
                self._queue.task_done()

    async def _process(self, signals: list[SignalEvent]) -> None:
        with new_span("router_process"):
            if not signals:
                return

            # Resolve YES/NO conflicts
            resolved = resolve_conflicts(signals)
            if resolved is None:
                return

            sample = resolved[0]
            condition_id = sample.condition_id
            token_id = sample.token_id
            side = sample.side

            # Check kill switch
            ks = await repo.get_kill_switch()
            if ks.get("triggered"):
                log.warning("router_kill_switch_active")
                return

            # Get current order book for price
            book = get_book(token_id)
            if book is None:
                log.warning("router_no_book", token_id=token_id[:12])
                # Fall back to leader price average
                avg_leader_price = sum(s.leader_price for s in resolved) / len(resolved)
                fok_price = avg_leader_price
            else:
                avg_leader_price = sum(s.leader_price for s in resolved) / len(resolved)
                fok_price = compute_fok_price(avg_leader_price, side, book)

            # Price band check: skip if outside [0.05, 0.95]
            if not (0.05 <= fok_price <= 0.95):
                log.info(
                    "router_price_out_of_band",
                    price=fok_price,
                    market=condition_id[:12],
                )
                return

            # Get bankroll
            metrics = await get_topline(self._mode)
            bankroll = metrics.equity_usd if metrics.equity_usd > 0 else 500.0

            shares = aggregate_signals_size(resolved, fok_price, bankroll)
            if shares <= 0:
                log.debug("router_zero_shares", market=condition_id[:12])
                return

            intent = build_order_intent(
                condition_id=condition_id,
                token_id=token_id,
                outcome=sample.outcome,
                side=side,
                leader_price=avg_leader_price,
                size_shares=shares,
                book=book,
                signal_ids=[s.id for s in resolved if s.id],
                leader_ranks=[s.leader_rank for s in resolved],
            )

            if intent is None:
                log.debug("router_intent_none", market=condition_id[:12])
                return

            log.info(
                "router_intent_built",
                market=condition_id[:12],
                side=side.value,
                price=intent.limit_price,
                shares=intent.size_shares,
                leaders=len(resolved),
            )
            self._on_intent(intent)
