"""Main bot runner — wires all async loops together."""
import asyncio
import signal
import structlog
from config.settings import (
    WALLET_HEALTH_CHECK_S,
    THESIS_BROKEN_SWEEP_S, TIME_STOP_SWEEP_S, EQUITY_SNAPSHOT_S,
)
from config.validators import validate_config
from config.secrets import get_secrets
from src.core.clock import now
from src.core.models import MarketMetadata
from src.core.exceptions import CircuitBreakerError, KillswitchError
from src.db.engine import init_engine, get_session_factory
from src.data.polymarket_client import get_client
from src.funnel.orchestrator import run_funnel_pipeline
from src.execution.queue import get_signal_queue
from src.execution.poller import WalletPoller
from src.execution.order_engine import OrderEngine
from src.execution.dedup import DedupRegistry
from src.execution.filters import run_all_filters
from src.execution.sizer import compute_tier, get_trade_params
from src.positions.tracker import open_position
from src.positions.pricer import PositionPricer
from src.positions.exiter import ExitHandler, check_thesis_broken, check_time_stop
from src.positions.reconciler import reconcile_positions
from src.risk.circuit_breakers import CircuitBreakerManager
from src.risk import killswitch
from src.db.repositories import PositionRepo, EquityRepo, WalletRepo
from src.db.models import EquitySnapshot as EquitySnapshotModel
from src.core.enums import WalletStatus

log = structlog.get_logger(__name__)

_shutdown = asyncio.Event()


def _install_signal_handlers() -> None:
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _shutdown.set())


class BotRunner:
    def __init__(self):
        self._session_factory = None
        self._poller: WalletPoller | None = None
        self._pricer: PositionPricer | None = None
        self._order_engine: OrderEngine | None = None
        self._dedup: DedupRegistry | None = None
        self._circuit_breakers: CircuitBreakerManager | None = None
        self._exit_handler: ExitHandler | None = None
        self._open_positions: list = []
        self._tasks: list[asyncio.Task] = []

    async def startup(self) -> None:
        log.info("bot_starting")
        validate_config()

        secrets = get_secrets()
        init_engine(secrets.database_url)
        get_client()  # initializes the singleton
        self._session_factory = get_session_factory()

        async with self._session_factory() as session:
            equity_repo = EquityRepo(session)
            last_snap = await equity_repo.get_last()
            initial_balance = last_snap.total_equity if last_snap else 1000.0

        self._circuit_breakers = CircuitBreakerManager(initial_balance)
        self._dedup = DedupRegistry()
        self._order_engine = OrderEngine()
        self._exit_handler = ExitHandler(self._order_engine, self._session_factory)
        self._pricer = PositionPricer()

        async with self._session_factory() as session:
            flagged = await reconcile_positions(session)
            if flagged:
                log.critical("startup_reconcile_failed", flagged=flagged)

        await self._refresh_open_positions()
        killswitch.start_monitor()
        log.info("bot_started", initial_balance=initial_balance)

    async def _get_active_addresses(self) -> list[str]:
        async with self._session_factory() as session:
            repo = WalletRepo(session)
            wallets = await repo.get_by_status(WalletStatus.ACTIVE)
            return [w.address for w in wallets]

    async def _get_shadow_addresses(self) -> list[str]:
        async with self._session_factory() as session:
            repo = WalletRepo(session)
            wallets = await repo.get_by_status(WalletStatus.SHADOW)
            return [w.address for w in wallets]

    async def _refresh_open_positions(self) -> None:
        async with self._session_factory() as session:
            pos_repo = PositionRepo(session)
            self._open_positions = await pos_repo.get_open(is_shadow=False)

    async def _process_signal_queue(self) -> None:
        """Consume live signal queue and execute trades."""
        queue = get_signal_queue()
        while not _shutdown.is_set():
            try:
                signal_event = await asyncio.wait_for(queue.live.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            try:
                killswitch.check_and_raise()
                async with self._session_factory() as session:
                    equity_repo = EquityRepo(session)
                    last_snap = await equity_repo.get_last()
                    equity = last_snap.total_equity if last_snap else 1000.0

                self._circuit_breakers.check_and_raise(equity)

                if self._dedup.is_duplicate(signal_event.market_id, signal_event.side):
                    log.debug("signal_deduped", market_id=signal_event.market_id)
                    continue

                async with self._session_factory() as session:
                    pos_repo = PositionRepo(session)
                    equity_repo = EquityRepo(session)
                    last_snap = await equity_repo.get_last()
                    bankroll = last_snap.total_equity if last_snap else 1000.0
                    deployed = await pos_repo.sum_deployed(is_shadow=False)
                    open_count = await pos_repo.count_open(is_shadow=False)

                tier = compute_tier(bankroll)
                trade_params = get_trade_params(tier)
                cash_balance = bankroll - deployed

                client = get_client()
                try:
                    market = await client.get_market_metadata(signal_event.market_id)
                    if not isinstance(market, MarketMetadata):
                        market = MarketMetadata(condition_id=signal_event.market_id, question="")
                except Exception:
                    market = MarketMetadata(condition_id=signal_event.market_id, question="")

                passed, fail_reason, filter_results = run_all_filters(
                    signal_event, market, cash_balance, trade_params, open_count,
                )
                if not passed:
                    log.info("signal_filtered", reason=str(fail_reason),
                             market_id=signal_event.market_id[:16],
                             lead_usd=round(signal_event.value_usd, 2),
                             market_vol=round(market.volume_24h_usd, 0),
                             price=signal_event.price)
                    continue

                self._dedup.lock(signal_event.market_id, signal_event.side)
                fill = await self._order_engine.place_buy(
                    signal_event, trade_params, market_volume_24h_usd=market.volume_24h_usd,
                    market_category=market.category,
                )

                async with self._session_factory() as session:
                    from src.db.models import Position as PositionModel, Wallet as WalletModel
                    from sqlalchemy import select
                    w = await session.scalar(
                        select(WalletModel).where(WalletModel.address == signal_event.wallet_address)
                    )
                    db_pos = PositionModel(
                        wallet_id=w.id if w else None,
                        market_id=signal_event.market_id,
                        token_id=signal_event.token_id,
                        side=signal_event.side,
                        entry_price=fill.fill_price,
                        size_shares=fill.fill_size_shares,
                        cost_usd=fill.cost_usd,
                        status="pending",
                        is_shadow=False,
                        opened_at=now(),
                    )
                    session.add(db_pos)
                    await session.flush()
                    log_entry = open_position(db_pos)
                    session.add(log_entry)
                    await session.commit()

                await self._refresh_open_positions()
                log.info("trade_executed", market_id=signal_event.market_id,
                         fill_price=fill.fill_price, size=fill.fill_size_shares)

            except (CircuitBreakerError, KillswitchError) as e:
                log.warning("trade_halted", reason=str(e))
            except Exception as e:
                log.error("signal_processing_error", error=str(e))

    async def _sweep_thesis_broken(self) -> None:
        while not _shutdown.is_set():
            await asyncio.sleep(THESIS_BROKEN_SWEEP_S)
            for pos in list(self._open_positions):
                try:
                    if check_thesis_broken(pos, pos.current_price or pos.entry_price, None):
                        await self._exit_handler.on_thesis_broken(pos)
                except Exception as e:
                    log.error("thesis_check_error", position_id=pos.id, error=str(e))
            await self._refresh_open_positions()

    async def _sweep_time_stop(self) -> None:
        while not _shutdown.is_set():
            await asyncio.sleep(TIME_STOP_SWEEP_S)
            for pos in list(self._open_positions):
                try:
                    if check_time_stop(pos):
                        await self._exit_handler.on_time_stop(pos)
                except Exception as e:
                    log.error("time_stop_check_error", position_id=pos.id, error=str(e))
            await self._refresh_open_positions()

    async def _equity_snapshot_loop(self) -> None:
        while not _shutdown.is_set():
            await asyncio.sleep(EQUITY_SNAPSHOT_S)
            try:
                async with self._session_factory() as session:
                    pos_repo = PositionRepo(session)
                    equity_repo = EquityRepo(session)
                    deployed = await pos_repo.sum_deployed(is_shadow=False)
                    unrealized = sum(
                        (p.unrealized_pnl_usd or 0.0) for p in self._open_positions
                    )
                    open_count = await pos_repo.count_open(is_shadow=False)
                    last = await equity_repo.get_last()
                    cash = (last.total_equity - deployed) if last else 1000.0
                    total = cash + deployed + unrealized
                    snap = EquitySnapshotModel(
                        timestamp=now(),
                        cash_balance=cash,
                        position_value=deployed + unrealized,
                        total_equity=total,
                        open_position_count=open_count,
                    )
                    session.add(snap)
                    await session.commit()
            except Exception as e:
                log.error("equity_snapshot_error", error=str(e))

    async def _funnel_loop(self) -> None:
        import traceback
        while not _shutdown.is_set():
            try:
                async with self._session_factory() as session:
                    await run_funnel_pipeline(session)
            except Exception as e:
                log.error("funnel_error", error=str(e), traceback=traceback.format_exc())
            await asyncio.sleep(WALLET_HEALTH_CHECK_S)

    async def _pricer_loop(self) -> None:
        def get_positions():
            return self._open_positions

        async def update_price(pos_id, price, unrealized):
            async with self._session_factory() as session:
                from sqlalchemy import update
                from src.db.models import Position as PositionModel
                await session.execute(
                    update(PositionModel)
                    .where(PositionModel.id == pos_id)
                    .values(current_price=price, unrealized_pnl_usd=unrealized)
                )
                await session.commit()

        await self._pricer.run(get_positions, update_price)

    async def _api_server(self) -> None:
        import uvicorn
        from src.api.main import app
        from config.settings import DASHBOARD_HOST, DASHBOARD_PORT
        config = uvicorn.Config(
            app,
            host=DASHBOARD_HOST,
            port=DASHBOARD_PORT,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        log.info("dashboard_starting", host=DASHBOARD_HOST, port=DASHBOARD_PORT)
        await server.serve()

    async def run(self) -> None:
        await self.startup()

        self._poller = WalletPoller()

        self._tasks = [
            asyncio.create_task(
                self._poller.run(self._get_active_addresses, self._get_shadow_addresses),
                name="poller",
            ),
            asyncio.create_task(self._process_signal_queue(), name="signal_consumer"),
            asyncio.create_task(self._pricer_loop(), name="pricer"),
            asyncio.create_task(self._sweep_thesis_broken(), name="thesis_sweep"),
            asyncio.create_task(self._sweep_time_stop(), name="time_stop_sweep"),
            asyncio.create_task(self._equity_snapshot_loop(), name="equity_snap"),
            asyncio.create_task(self._funnel_loop(), name="funnel"),
            asyncio.create_task(self._api_server(), name="api"),
        ]

        log.info("all_loops_started", count=len(self._tasks))
        await _shutdown.wait()
        await self.shutdown()

    async def shutdown(self) -> None:
        log.info("bot_shutting_down")
        killswitch.stop_monitor()
        if self._poller:
            self._poller.stop()
        if self._pricer:
            self._pricer.stop()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        log.info("bot_stopped")


async def run_bot() -> None:
    _install_signal_handlers()
    runner = BotRunner()
    await runner.run()
