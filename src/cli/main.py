"""Click CLI — operator control surface for the Polymarket copy bot."""
import asyncio
import click
import json


def _run(coro):
    return asyncio.run(coro)


def _get_session():
    from src.db.engine import get_session_factory
    return get_session_factory()


# ─── Root ────────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """Polymarket Copy Bot v2.3 — operator CLI."""


# ─── status ──────────────────────────────────────────────────────────────────

@cli.command()
def status():
    """Show current bot state (one-screen summary)."""
    async def _inner():
        from config.validators import validate_config
        from config.secrets import get_secrets
        from src.db.engine import init_engine, get_session_factory
        from src.db.repositories import PositionRepo, EquityRepo, WalletRepo
        from src.core.enums import WalletStatus
        secrets = get_secrets()
        init_engine(secrets.database_url)
        sf = get_session_factory()
        async with sf() as session:
            w_repo = WalletRepo(session)
            p_repo = PositionRepo(session)
            e_repo = EquityRepo(session)
            active = await w_repo.get_by_status(WalletStatus.ACTIVE)
            shadow = await w_repo.get_by_status(WalletStatus.SHADOW)
            open_pos = await p_repo.count_open(is_shadow=False)
            deployed = await p_repo.sum_deployed(is_shadow=False)
            snap = await e_repo.get_last()
            equity = snap.total_equity if snap else 0.0
        click.echo(f"  Active wallets : {len(active)}")
        click.echo(f"  Shadow wallets : {len(shadow)}")
        click.echo(f"  Open positions : {open_pos}")
        click.echo(f"  Deployed       : ${deployed:,.2f}")
        click.echo(f"  Total equity   : ${equity:,.2f}")
    _run(_inner())


# ─── start ───────────────────────────────────────────────────────────────────

@cli.command()
def start():
    """Start the bot runner (foreground)."""
    import threading, webbrowser, time
    from config.settings import DASHBOARD_PORT
    def _open_browser():
        time.sleep(2)
        webbrowser.open(f"http://localhost:{DASHBOARD_PORT}")
    threading.Thread(target=_open_browser, daemon=True).start()
    from src.runner import run_bot
    _run(run_bot())


# ─── wallets ─────────────────────────────────────────────────────────────────

@cli.group()
def wallets():
    """Wallet management."""


@wallets.command("list")
@click.option("--status", "status_filter", default="active",
              type=click.Choice(["candidate", "shadow", "active", "bench", "suspended", "dropped", "disqualified"]))
def wallets_list(status_filter):
    """List wallets by status."""
    async def _inner():
        from config.secrets import get_secrets
        from src.db.engine import init_engine, get_session_factory
        from src.db.repositories import WalletRepo
        from src.core.enums import WalletStatus
        secrets = get_secrets()
        init_engine(secrets.database_url)
        sf = get_session_factory()
        async with sf() as session:
            repo = WalletRepo(session)
            ws = await repo.get_by_status(WalletStatus(status_filter))
        if not ws:
            click.echo(f"No wallets with status '{status_filter}'.")
            return
        for w in ws:
            click.echo(f"  {w.address}  score={w.composite_score or 0:.2f}")
    _run(_inner())


@wallets.command("show")
@click.argument("address")
def wallets_show(address):
    """Show full wallet metrics."""
    async def _inner():
        from config.secrets import get_secrets
        from src.db.engine import init_engine, get_session_factory
        from src.db.repositories import WalletRepo
        secrets = get_secrets()
        init_engine(secrets.database_url)
        sf = get_session_factory()
        async with sf() as session:
            repo = WalletRepo(session)
            w = await repo.get_by_address(address)
        if not w:
            click.echo(f"Wallet {address} not found.")
            return
        click.echo(json.dumps({
            "address": w.address,
            "status": w.status,
            "composite_score": w.composite_score,
            "win_rate": w.win_rate,
            "profit_factor": w.profit_factor,
            "closed_trades_count": w.closed_trades_count,
        }, indent=2))
    _run(_inner())


@wallets.command("suspend")
@click.argument("address")
@click.option("--confirm", is_flag=True, required=True, help="Required to mutate.")
def wallets_suspend(address, confirm):
    """Manually suspend a wallet."""
    async def _inner():
        from config.secrets import get_secrets
        from src.db.engine import init_engine, get_session_factory
        from src.db.repositories import WalletRepo
        from src.core.enums import WalletStatus
        secrets = get_secrets()
        init_engine(secrets.database_url)
        sf = get_session_factory()
        async with sf() as session:
            repo = WalletRepo(session)
            await repo.update_status(address, WalletStatus.SUSPENDED)
            await session.commit()
        click.echo(f"Wallet {address} suspended.")
    _run(_inner())


@wallets.command("promote")
@click.argument("address")
@click.option("--confirm", is_flag=True, required=True)
def wallets_promote(address, confirm):
    """Force-promote a wallet to active."""
    async def _inner():
        from config.secrets import get_secrets
        from src.db.engine import init_engine, get_session_factory
        from src.db.repositories import WalletRepo
        from src.core.enums import WalletStatus
        secrets = get_secrets()
        init_engine(secrets.database_url)
        sf = get_session_factory()
        async with sf() as session:
            repo = WalletRepo(session)
            await repo.update_status(address, WalletStatus.ACTIVE)
            await session.commit()
        click.echo(f"Wallet {address} promoted to active.")
    _run(_inner())


# ─── positions ───────────────────────────────────────────────────────────────

@cli.group()
def positions():
    """Position management."""


@positions.command("list")
def positions_list():
    """List open positions."""
    async def _inner():
        from config.secrets import get_secrets
        from src.db.engine import init_engine, get_session_factory
        from src.db.repositories import PositionRepo
        secrets = get_secrets()
        init_engine(secrets.database_url)
        sf = get_session_factory()
        async with sf() as session:
            repo = PositionRepo(session)
            ps = await repo.get_open(is_shadow=False)
        if not ps:
            click.echo("No open positions.")
            return
        for p in ps:
            pnl = p.unrealized_pnl_usd or 0.0
            click.echo(f"  [{p.id}] {p.market_id[:40]}  entry={p.entry_price:.3f}  pnl=${pnl:+.2f}")
    _run(_inner())


@positions.command("show")
@click.argument("position_id", type=int)
def positions_show(position_id):
    """Show position details."""
    async def _inner():
        from config.secrets import get_secrets
        from src.db.engine import init_engine, get_session_factory
        from sqlalchemy import select
        from src.db.models import Position as PositionModel
        secrets = get_secrets()
        init_engine(secrets.database_url)
        sf = get_session_factory()
        async with sf() as session:
            p = await session.scalar(select(PositionModel).where(PositionModel.id == position_id))
        if not p:
            click.echo(f"Position {position_id} not found.")
            return
        click.echo(json.dumps({
            "id": p.id, "market_id": p.market_id, "side": p.side,
            "entry_price": p.entry_price, "size_shares": p.size_shares,
            "cost_usd": p.cost_usd, "unrealized_pnl_usd": p.unrealized_pnl_usd,
            "status": p.status,
        }, indent=2))
    _run(_inner())


@positions.command("exit")
@click.argument("position_id", type=int)
@click.option("--confirm", is_flag=True, required=True)
def positions_exit(position_id, confirm):
    """Force-exit a position."""
    async def _inner():
        from config.secrets import get_secrets
        from src.db.engine import init_engine, get_session_factory
        from sqlalchemy import select
        from src.db.models import Position as PositionModel
        from src.execution.order_engine import OrderEngine
        from src.positions.exiter import ExitHandler
        secrets = get_secrets()
        init_engine(secrets.database_url)
        sf = get_session_factory()
        engine = OrderEngine()
        handler = ExitHandler(engine, sf)
        async with sf() as session:
            p = await session.scalar(select(PositionModel).where(PositionModel.id == position_id))
        if not p:
            click.echo(f"Position {position_id} not found.")
            return
        await handler.on_manual(p)
        click.echo(f"Position {position_id} exit submitted.")
    _run(_inner())


@positions.command("exit-all")
@click.option("--confirm", is_flag=True, required=True)
def positions_exit_all(confirm):
    """Force-exit all open positions."""
    async def _inner():
        from config.secrets import get_secrets
        from src.db.engine import init_engine, get_session_factory
        from src.db.repositories import PositionRepo
        from src.execution.order_engine import OrderEngine
        from src.positions.exiter import ExitHandler
        secrets = get_secrets()
        init_engine(secrets.database_url)
        sf = get_session_factory()
        engine = OrderEngine()
        handler = ExitHandler(engine, sf)
        async with sf() as session:
            repo = PositionRepo(session)
            ps = await repo.get_open(is_shadow=False)
        for p in ps:
            await handler.on_manual(p)
        click.echo(f"Exited {len(ps)} position(s).")
    _run(_inner())


# ─── tier ────────────────────────────────────────────────────────────────────

@cli.group()
def tier():
    """Tier management."""


@tier.command("show")
def tier_show():
    """Show current tier and trade params."""
    async def _inner():
        from config.secrets import get_secrets
        from src.db.engine import init_engine, get_session_factory
        from src.db.repositories import EquityRepo
        from src.execution.sizer import compute_tier, get_trade_params
        secrets = get_secrets()
        init_engine(secrets.database_url)
        sf = get_session_factory()
        async with sf() as session:
            repo = EquityRepo(session)
            snap = await repo.get_last()
            bankroll = snap.total_equity if snap else 1000.0
        tp = get_trade_params(compute_tier(bankroll))
        click.echo(f"  Tier           : {tp.tier}")
        click.echo(f"  Trade size     : ${tp.trade_size_usd:.2f}")
        click.echo(f"  Max positions  : {tp.max_positions}")
        click.echo(f"  Max deployed   : {tp.max_deployed_pct:.0%}")
        click.echo(f"  Bankroll       : ${bankroll:,.2f}")
    _run(_inner())


@tier.command("set")
@click.argument("tier_n", type=int)
@click.option("--confirm", is_flag=True, required=True)
def tier_set(tier_n, confirm):
    """Override tier (sets TIER_OVERRIDE env var hint)."""
    click.echo(f"Set TIER_OVERRIDE={tier_n} in your .env file to apply the override.")
    click.echo("Restart the bot for the change to take effect.")


# ─── funnel ──────────────────────────────────────────────────────────────────

@cli.group()
def funnel():
    """Wallet funnel management."""


@funnel.command("run")
@click.option("--dry-run", is_flag=True, default=False)
def funnel_run(dry_run):
    """Force the funnel pipeline to run now."""
    async def _inner():
        from config.secrets import get_secrets
        from src.db.engine import init_engine, get_session_factory
        from src.data.polymarket_client import get_client
        from src.funnel.orchestrator import run_funnel_pipeline
        secrets = get_secrets()
        init_engine(secrets.database_url)
        get_client()
        sf = get_session_factory()
        summary = await run_funnel_pipeline(sf, dry_run=dry_run)
        click.echo(json.dumps(summary, indent=2, default=str))
    _run(_inner())


@funnel.command("show")
def funnel_show():
    """Show current funnel state (wallet counts by stage)."""
    async def _inner():
        from config.secrets import get_secrets
        from src.db.engine import init_engine, get_session_factory
        from src.db.repositories import WalletRepo
        from src.core.enums import WalletStatus
        secrets = get_secrets()
        init_engine(secrets.database_url)
        sf = get_session_factory()
        async with sf() as session:
            repo = WalletRepo(session)
            counts = {}
            for s in WalletStatus:
                ws = await repo.get_by_status(s)
                counts[s.value] = len(ws)
        click.echo(json.dumps(counts, indent=2))
    _run(_inner())


# ─── killswitch ──────────────────────────────────────────────────────────────

@cli.group()
def killswitch():
    """Emergency killswitch."""


@killswitch.command("on")
@click.option("--confirm", is_flag=True, required=True)
def killswitch_on(confirm):
    """Halt all new entries (set KILLSWITCH=1 in .env then restart)."""
    click.echo("Set KILLSWITCH=1 in your .env file.")
    click.echo("The running bot will pick this up within 15 seconds.")


@killswitch.command("off")
@click.option("--confirm", is_flag=True, required=True)
def killswitch_off(confirm):
    """Re-enable new entries (remove KILLSWITCH from .env)."""
    click.echo("Remove or set KILLSWITCH=0 in your .env file.")
    click.echo("The running bot will pick this up within 15 seconds.")


# ─── config ──────────────────────────────────────────────────────────────────

@cli.group("config")
def config_group():
    """Configuration management."""


@config_group.command("show")
def config_show():
    """Print current config values."""
    import config.settings as s
    fields = [f for f in dir(s) if f.isupper() and not f.startswith("_")]
    for f in sorted(fields):
        click.echo(f"  {f} = {getattr(s, f)}")


@config_group.command("validate")
def config_validate():
    """Validate all configuration settings."""
    from config.validators import validate_config
    try:
        validate_config()
        click.echo("Config OK — all assertions passed.")
    except Exception as e:
        click.echo(f"Config FAILED: {e}", err=True)
        raise SystemExit(1)


# ─── db ──────────────────────────────────────────────────────────────────────

@cli.group()
def db():
    """Database management."""


@db.command("migrate")
def db_migrate():
    """Run Alembic migrations (upgrade head)."""
    import subprocess
    result = subprocess.run(["uv", "run", "alembic", "upgrade", "head"], capture_output=False)
    raise SystemExit(result.returncode)


@db.command("backup")
@click.argument("path")
def db_backup(path):
    """Backup the database (pg_dump)."""
    import subprocess
    from config.secrets import get_secrets
    url = get_secrets().database_url
    result = subprocess.run(["pg_dump", url, "-f", path], capture_output=False)
    if result.returncode == 0:
        click.echo(f"Backup written to {path}")
    else:
        click.echo("Backup failed.", err=True)
        raise SystemExit(1)
