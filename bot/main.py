"""
Main entrypoint — wires all components and starts the asyncio event loop.
Usage: uv run python -m bot.main
"""
from __future__ import annotations

import asyncio
import signal
import sys

import uvicorn

from bot.api.server import app
from bot.api.ws import run_fanout
from bot.clob.ws_market import MarketWebSocket
from bot.clob.ws_user import UserWebSocket
from bot.config import get_settings
from bot.data.data_api import DataAPIClient
from bot.discovery.job import schedule_daily_discovery
from bot.engine.aggregator import SignalAggregator
from bot.engine.executor import execute_order
from bot.engine.exits import ExitMonitor
from bot.engine.recovery import reconcile_on_startup
from bot.engine.router import OrderRouter
from bot.engine.signals import SignalDetector
from bot.ledger.db import init_db
from bot.models import OrderIntent, SignalEvent
from bot.observability.log import configure_logging, get_logger
from bot.observability.trace import new_trace

log = get_logger(__name__)

_shutdown_event = asyncio.Event()


def _handle_signal(sig: signal.Signals) -> None:
    log.info("shutdown_signal_received", signal=sig.name)
    _shutdown_event.set()


async def main() -> None:
    configure_logging()
    cfg = get_settings()

    log.info("bot_starting", mode=cfg.bot_mode, version="2.0.0")

    # 1. Init database
    await init_db()
    log.info("database_ready")

    async with DataAPIClient() as client:

        # 2. Crash recovery
        await reconcile_on_startup(client, cfg.bot_mode)

        # 3. Wire execution pipeline
        async def on_intent(intent: OrderIntent) -> None:
            await execute_order(intent, cfg.bot_mode)

        async def on_intent_sync(intent: OrderIntent) -> None:
            asyncio.get_running_loop().create_task(on_intent(intent))

        router = OrderRouter(on_intent=on_intent_sync, mode=cfg.bot_mode)
        aggregator = SignalAggregator(on_flush=router.enqueue)

        async def on_signal(signal_event: SignalEvent) -> None:
            aggregator.ingest(signal_event)

        detector = SignalDetector(client=client, on_signal=on_signal)

        async def on_exit_signal(signal_event: SignalEvent) -> None:
            aggregator.ingest(signal_event)

        exit_monitor = ExitMonitor(
            client=client,
            on_exit_signal=on_exit_signal,
            mode=cfg.bot_mode,
        )

        # 4. CLOB WebSocket connections
        # MarketWebSocket starts with no subscriptions; signal detector subscribes dynamically
        market_ws = MarketWebSocket(token_ids=[])

        # 5. Configure uvicorn
        uvicorn_config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=8787,
            log_level="warning",
            access_log=False,
        )
        uvicorn_server = uvicorn.Server(uvicorn_config)

        # Register OS signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _handle_signal, sig)
            except NotImplementedError:
                # Windows — use signal.signal instead
                signal.signal(sig, lambda s, f: _handle_signal(signal.Signals(s)))

        log.info("starting_all_tasks")

        # 6. Launch everything concurrently
        # UserWebSocket requires CLOB credentials — only start in LIVE mode
        tasks = [
            asyncio.create_task(detector.start(), name="signal_detector"),
            asyncio.create_task(aggregator.run(), name="aggregator"),
            asyncio.create_task(router.run(), name="router"),
            asyncio.create_task(exit_monitor.run(), name="exit_monitor"),
            asyncio.create_task(market_ws.run(), name="market_ws"),
            asyncio.create_task(schedule_daily_discovery(), name="discovery"),
            asyncio.create_task(run_fanout(), name="ws_fanout"),
            asyncio.create_task(uvicorn_server.serve(), name="api_server"),
            asyncio.create_task(_shutdown_event.wait(), name="shutdown_watcher"),
        ]

        if cfg.bot_mode == "LIVE":
            user_ws = UserWebSocket(
                market_condition_ids=[],
                on_fill=lambda ev: log.info("user_ws_fill", event=ev),
            )
            tasks.append(asyncio.create_task(user_ws.run(), name="user_ws"))

        log.info("bot_running", api="http://127.0.0.1:8787", mode=cfg.bot_mode)

        # Wait for shutdown signal or any task to crash
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        for task in done:
            if task.get_name() != "shutdown_watcher" and not task.cancelled():
                exc = task.exception()
                if exc:
                    log.error("task_crashed", task=task.get_name(), error=str(exc))

        # Graceful shutdown
        log.info("shutdown_start")
        aggregator.stop()
        await detector.stop()
        exit_monitor.stop()
        uvicorn_server.should_exit = True

        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        log.info("shutdown_complete")


def cli() -> None:
    """Entry point for `polymarket-bot` CLI command."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()
