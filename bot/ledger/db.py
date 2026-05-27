import time
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from bot.config import get_settings


async def init_db() -> None:
    cfg = get_settings()
    path = Path(cfg.database_path)
    async with aiosqlite.connect(path) as db:
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        await db.executescript(schema)
        await db.execute("PRAGMA journal_mode=WAL;")
        migrations = [
            "ALTER TABLE leaders ADD COLUMN pnl_30d REAL NOT NULL DEFAULT 0",
            "ALTER TABLE leaders ADD COLUMN win_rate REAL NOT NULL DEFAULT 0",
            "ALTER TABLE leaders ADD COLUMN trade_count_30d INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE leaders ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
            "ALTER TABLE leaders ADD COLUMN cluster_id TEXT",
            "ALTER TABLE account_state ADD COLUMN starting_equity_usd REAL NOT NULL DEFAULT 100",
            "ALTER TABLE account_state ADD COLUMN daily_pnl_usd REAL NOT NULL DEFAULT 0",
            "ALTER TABLE account_state ADD COLUMN kill_switch_triggered INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE positions ADD COLUMN leader_proxy TEXT",
            "ALTER TABLE positions ADD COLUMN outcome TEXT DEFAULT ''",
            "ALTER TABLE positions ADD COLUMN redeemable INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE discovery_runs ADD COLUMN standby INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE fills ADD COLUMN exchange_order_id TEXT",
            """CREATE TABLE IF NOT EXISTS leader_cursors (
              proxy TEXT PRIMARY KEY,
              last_event_ts INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            )""",
        ]
        for ddl in migrations:
            try:
                await db.execute(ddl)
            except Exception:
                pass
        await db.execute(
            "INSERT OR IGNORE INTO account_state (id, cash_usd, equity_usd, starting_equity_usd, updated_at) VALUES (1, ?, ?, ?, ?)",
            (cfg.starting_bankroll_usd, cfg.starting_bankroll_usd, cfg.starting_bankroll_usd, int(time.time())),
        )
        await db.commit()


@asynccontextmanager
async def get_db():
    conn = await aiosqlite.connect(get_settings().database_path)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()
