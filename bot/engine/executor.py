"""
Executor: the single execute_order() function.
Dispatches to paper fill engine or live CLOB based on mode.
Records fills, updates positions, checks kill switch after every fill.
"""
from __future__ import annotations

import time

from bot.config import get_settings
from bot.ledger import repo
from bot.ledger.db import write_event
from bot.models import FillResult, Mode, OrderIntent, OrderStatus
from bot.observability.log import get_logger
from bot.observability.trace import new_span

log = get_logger(__name__)


async def execute_order(intent: OrderIntent, mode: str) -> FillResult | None:
    """
    The single entry point for all order execution.
    Routes to paper or live fill engine, persists results, checks kill switch.
    """
    with new_span("execute_order"):
        log.info(
            "execute_order_start",
            mode=mode,
            market=intent.condition_id[:12],
            side=intent.side.value,
            price=intent.limit_price,
            shares=intent.size_shares,
            client_order_id=intent.client_order_id,
        )

        if mode == Mode.PAPER:
            result = await _paper_fill(intent)
        else:
            result = await _live_fill(intent)

        if result is None:
            log.info("execute_order_rejected", client_order_id=intent.client_order_id)
            return None

        # Persist fill
        await repo.insert_fill(result, mode)

        # Update or open position
        await _update_position(intent, result, mode)

        # Check daily kill switch
        await _check_kill_switch(mode)

        await write_event(
            "order_filled" if result.status == OrderStatus.FILLED else "order_rejected",
            {
                "client_order_id": result.client_order_id,
                "filled_shares": result.filled_shares,
                "avg_price": result.avg_price,
                "fee_usd": result.fee_usd,
                "mode": mode,
            },
        )

        log.info(
            "execute_order_done",
            status=result.status.value,
            filled=result.filled_shares,
            avg_price=result.avg_price,
            fee=result.fee_usd,
        )
        return result


async def _paper_fill(intent: OrderIntent) -> FillResult | None:
    from bot.paper.fill_engine import simulate_fill
    return await simulate_fill(intent)


async def _live_fill(intent: OrderIntent) -> FillResult | None:
    from bot.clob.client import clob_client
    try:
        return await clob_client.create_and_post_order(intent)
    except Exception as e:
        log.error("live_fill_error", error=str(e), client_order_id=intent.client_order_id)
        return None


async def _update_position(intent: OrderIntent, result: FillResult, mode: str) -> None:
    from bot.models import OrderSide
    if result.status != OrderStatus.FILLED or result.filled_shares <= 0:
        return

    cost_usd = result.filled_shares * result.avg_price + result.fee_usd

    existing = await repo.get_position(intent.condition_id, intent.token_id, mode)

    if intent.side == OrderSide.BUY:
        if existing:
            await repo.add_to_position(
                condition_id=intent.condition_id,
                token_id=intent.token_id,
                added_shares=result.filled_shares,
                added_cost=cost_usd,
                mode=mode,
            )
        else:
            await repo.open_position(
                condition_id=intent.condition_id,
                token_id=intent.token_id,
                outcome=intent.outcome,
                side=intent.side.value,
                shares=result.filled_shares,
                cost_usd=cost_usd,
                entry_price=result.avg_price,
                mode=mode,
                signal_ids=intent.signal_ids,
                leader_ranks=intent.leader_ranks,
            )
    else:  # SELL
        if existing:
            realized_pnl = (result.avg_price - existing["avg_entry_price"]) * result.filled_shares - result.fee_usd
            await repo.reduce_position(
                condition_id=intent.condition_id,
                token_id=intent.token_id,
                sold_shares=result.filled_shares,
                proceeds_usd=result.filled_shares * result.avg_price - result.fee_usd,
                realized_pnl=realized_pnl,
                mode=mode,
            )


async def _check_kill_switch(mode: str) -> None:
    cfg = get_settings()
    ks = await repo.get_kill_switch()
    if ks.get("triggered"):
        return

    daily_loss = await repo.get_daily_loss(mode)
    threshold = cfg.kill_switch_daily_loss_usd

    if daily_loss >= threshold:
        await repo.trigger_kill_switch(
            reason=f"daily_loss_{daily_loss:.2f}_exceeds_{threshold:.2f}"
        )
        log.error(
            "kill_switch_triggered",
            daily_loss=daily_loss,
            threshold=threshold,
        )
