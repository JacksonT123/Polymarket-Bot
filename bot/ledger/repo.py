"""
Data access layer — all SQL in one place.
All functions are async and open their own db connection via get_db().
"""
from __future__ import annotations

import json
import time
from datetime import date

import aiosqlite

from bot.ledger.db import get_db
from bot.models import (
    FillResult,
    Leader,
    LeaderStatus,
    LeaderTier,
    OrderStatus,
    SignalEvent,
)


# ── Leader roster ──────────────────────────────────────────────────────────────

async def get_roster(snapshot_date: str | None = None) -> list[Leader]:
    """Return today's full roster (active + standby), ordered by rank."""
    day = snapshot_date or str(date.today())
    async with get_db() as db:
        async with db.execute(
            """SELECT proxy_address, rank, tier, score, score_delta, status, cold_since_ts
               FROM leader_rosters WHERE snapshot_date=? ORDER BY rank ASC""",
            (day,),
        ) as cur:
            rows = await cur.fetchall()
    return [_row_to_leader(r, day) for r in rows]


async def get_active_leaders() -> list[Leader]:
    """Return only ACTIVE tier leaders from today's roster."""
    day = str(date.today())
    async with get_db() as db:
        async with db.execute(
            """SELECT proxy_address, rank, tier, score, score_delta, status, cold_since_ts
               FROM leader_rosters
               WHERE snapshot_date=? AND tier='active' AND status='active'
               ORDER BY rank ASC""",
            (day,),
        ) as cur:
            rows = await cur.fetchall()
    return [_row_to_leader(r, day) for r in rows]


async def upsert_roster(leaders: list[Leader]) -> None:
    async with get_db() as db:
        await db.executemany(
            """INSERT INTO leader_rosters
               (snapshot_date, proxy_address, rank, tier, score, score_delta, status, cold_since_ts)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(snapshot_date, proxy_address) DO UPDATE SET
               rank=excluded.rank, tier=excluded.tier, score=excluded.score,
               score_delta=excluded.score_delta, status=excluded.status""",
            [
                (l.snapshot_date, l.proxy_address, l.rank, l.tier.value,
                 l.score, l.score_delta, l.status.value, l.cold_since_ts)
                for l in leaders
            ],
        )
        await db.commit()


def _row_to_leader(r, snapshot_date: str) -> Leader:
    return Leader(
        proxy_address=r[0] if isinstance(r, tuple) else r["proxy_address"],
        rank=r[1] if isinstance(r, tuple) else r["rank"],
        tier=LeaderTier(r[2] if isinstance(r, tuple) else r["tier"]),
        score=r[3] if isinstance(r, tuple) else r["score"],
        score_delta=(r[4] if isinstance(r, tuple) else r["score_delta"]) or 0.0,
        status=LeaderStatus((r[5] if isinstance(r, tuple) else r["status"])),
        cold_since_ts=r[6] if isinstance(r, tuple) else r["cold_since_ts"],
        snapshot_date=snapshot_date,
    )


# ── Signals ────────────────────────────────────────────────────────────────────

async def insert_signal(signal: SignalEvent) -> None:
    ts = int(time.time())
    async with get_db() as db:
        await db.execute(
            """INSERT OR IGNORE INTO leader_signals
               (id, detected_at, leader_proxy, leader_rank, condition_id, token_id,
                outcome, side, leader_price, leader_size, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (signal.id, ts, signal.proxy_address, signal.leader_rank,
             signal.condition_id, signal.token_id, signal.outcome,
             signal.side.value, signal.leader_price, signal.leader_size,
             signal.status.value),
        )
        await db.commit()


async def get_signals_for_leader(proxy: str, limit: int = 50) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT * FROM leader_signals WHERE leader_proxy=?
               ORDER BY detected_at DESC LIMIT ?""",
            (proxy, limit),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ── Fills ──────────────────────────────────────────────────────────────────────

async def insert_fill(result: FillResult, mode: str) -> None:
    table = "paper_fills" if mode == "PAPER" else "live_fills"
    async with get_db() as db:
        await db.execute(
            f"""INSERT OR IGNORE INTO {table}
                (client_order_id, exchange_order_id, status, filled_shares, avg_price,
                 fee_usd, filled_at_ts, reject_reason)
                VALUES (?,?,?,?,?,?,?,?)""",
            (result.client_order_id, result.exchange_order_id, result.status.value,
             result.filled_shares, result.avg_price, result.fee_usd,
             result.filled_at_ts, result.reject_reason),
        )
        await db.commit()


# ── Positions ──────────────────────────────────────────────────────────────────

async def get_position(condition_id: str, token_id: str, mode: str) -> dict | None:
    table = "paper_positions" if mode == "PAPER" else "live_positions"
    async with get_db() as db:
        async with db.execute(
            f"SELECT * FROM {table} WHERE condition_id=? AND token_id=? AND is_open=1",
            (condition_id, token_id),
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def get_open_positions(mode: str) -> list[dict]:
    table = "paper_positions" if mode == "PAPER" else "live_positions"
    async with get_db() as db:
        async with db.execute(f"SELECT * FROM {table} WHERE is_open=1 ORDER BY opened_at_ts DESC") as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["leader_ranks"] = json.loads(d.pop("leader_ranks_json") or "[]")
        d["signal_ids"] = json.loads(d.pop("signal_ids_json") or "[]")
        d.setdefault("current_price", None)
        d.setdefault("current_value_usd", None)
        d.setdefault("unrealized_pnl_usd", None)
        result.append(d)
    return result


async def get_closed_positions(mode: str, limit: int = 100, offset: int = 0) -> list[dict]:
    table = "paper_positions" if mode == "PAPER" else "live_positions"
    async with get_db() as db:
        async with db.execute(
            f"SELECT * FROM {table} WHERE is_open=0 ORDER BY closed_at_ts DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["leader_ranks"] = json.loads(d.pop("leader_ranks_json") or "[]")
        d["signal_ids"] = json.loads(d.pop("signal_ids_json") or "[]")
        d["realized_pnl_usd"] = d.pop("realized_pnl") or 0.0
        result.append(d)
    return result


async def open_position(
    condition_id: str,
    token_id: str,
    outcome: str,
    side: str,
    shares: float,
    cost_usd: float,
    entry_price: float,
    mode: str,
    signal_ids: list[str],
    leader_ranks: list[int],
) -> None:
    table = "paper_positions" if mode == "PAPER" else "live_positions"
    ts = int(time.time())
    async with get_db() as db:
        await db.execute(
            f"""INSERT INTO {table}
                (condition_id, token_id, outcome, side, shares, cost_usd, avg_entry_price,
                 opened_at_ts, is_open, signal_ids_json, leader_ranks_json)
                VALUES (?,?,?,?,?,?,?,?,1,?,?)""",
            (condition_id, token_id, outcome, side, shares, cost_usd, entry_price,
             ts, json.dumps(signal_ids), json.dumps(leader_ranks)),
        )
        await db.commit()


async def add_to_position(
    condition_id: str,
    token_id: str,
    added_shares: float,
    added_cost: float,
    mode: str,
) -> None:
    table = "paper_positions" if mode == "PAPER" else "live_positions"
    async with get_db() as db:
        await db.execute(
            f"""UPDATE {table}
                SET shares = shares + ?,
                    cost_usd = cost_usd + ?,
                    avg_entry_price = (cost_usd + ?) / (shares + ?)
                WHERE condition_id=? AND token_id=? AND is_open=1""",
            (added_shares, added_cost, added_cost, added_shares,
             condition_id, token_id),
        )
        await db.commit()


async def reduce_position(
    condition_id: str,
    token_id: str,
    sold_shares: float,
    proceeds_usd: float,
    realized_pnl: float,
    mode: str,
    exit_price: float | None = None,
    exit_reason: str | None = None,
) -> None:
    table = "paper_positions" if mode == "PAPER" else "live_positions"
    ts = int(time.time())
    async with get_db() as db:
        async with db.execute(
            f"SELECT shares FROM {table} WHERE condition_id=? AND token_id=? AND is_open=1",
            (condition_id, token_id),
        ) as cur:
            row = await cur.fetchone()

        if not row:
            return

        remaining = row[0] - sold_shares

        if remaining <= 0.001:
            await db.execute(
                f"""UPDATE {table}
                    SET is_open=0, shares=0, closed_at_ts=?, realized_pnl=?,
                        exit_price=?, proceeds_usd=?, exit_reason=?
                    WHERE condition_id=? AND token_id=? AND is_open=1""",
                (ts, realized_pnl, exit_price, proceeds_usd, exit_reason,
                 condition_id, token_id),
            )
        else:
            await db.execute(
                f"""UPDATE {table}
                    SET shares=?, cost_usd=cost_usd - ?
                    WHERE condition_id=? AND token_id=? AND is_open=1""",
                (remaining, proceeds_usd, condition_id, token_id),
            )
        await db.commit()


async def mark_position_externally_closed(condition_id: str, token_id: str, mode: str) -> None:
    table = "paper_positions" if mode == "PAPER" else "live_positions"
    ts = int(time.time())
    async with get_db() as db:
        await db.execute(
            f"""UPDATE {table}
                SET is_open=0, closed_at_ts=?, exit_reason='external'
                WHERE condition_id=? AND token_id=? AND is_open=1""",
            (ts, condition_id, token_id),
        )
        await db.commit()


# ── Trades (order records) ─────────────────────────────────────────────────────

async def expire_stale_orders(cutoff_ts: int, mode: str) -> int:
    table = "paper_trades" if mode == "PAPER" else "live_trades"
    async with get_db() as db:
        async with db.execute(
            f"""UPDATE {table} SET status='EXPIRED'
                WHERE status IN ('PENDING','SUBMITTED') AND created_at < ?""",
            (cutoff_ts,),
        ) as cur:
            count = cur.rowcount
        await db.commit()
    return count


# ── Kill switch ────────────────────────────────────────────────────────────────

async def get_kill_switch() -> dict:
    async with get_db() as db:
        async with db.execute(
            "SELECT triggered, triggered_at, reason, daily_loss_usd, daily_loss_limit_usd FROM kill_switch WHERE id=1"
        ) as cur:
            r = await cur.fetchone()
    if not r:
        return {"triggered": False, "reason": None}
    return {
        "triggered": bool(r[0]),
        "triggered_at": r[1],
        "reason": r[2],
        "daily_loss_usd": r[3],
        "daily_loss_limit_usd": r[4],
    }


async def trigger_kill_switch(reason: str) -> None:
    ts = int(time.time())
    async with get_db() as db:
        await db.execute(
            "UPDATE kill_switch SET triggered=1, triggered_at=?, reason=? WHERE id=1",
            (ts, reason),
        )
        await db.commit()


async def reset_kill_switch() -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE kill_switch SET triggered=0, triggered_at=NULL, reason=NULL, daily_loss_usd=0 WHERE id=1"
        )
        await db.commit()


async def get_daily_loss(mode: str) -> float:
    """Sum of realized losses today in the given mode's position table."""
    table = "paper_positions" if mode == "PAPER" else "live_positions"
    today_midnight = int(time.time()) - (int(time.time()) % 86400)
    async with get_db() as db:
        async with db.execute(
            f"""SELECT COALESCE(SUM(CASE WHEN realized_pnl < 0 THEN ABS(realized_pnl) ELSE 0 END), 0)
                FROM {table} WHERE is_open=0 AND closed_at_ts >= ?""",
            (today_midnight,),
        ) as cur:
            row = await cur.fetchone()
    return float(row[0]) if row else 0.0


# ── Equity snapshots ───────────────────────────────────────────────────────────

async def insert_equity_snapshot(
    equity_usd: float,
    cash_usd: float,
    positions_usd: float,
    mode: str,
) -> None:
    ts = int(time.time())
    async with get_db() as db:
        await db.execute(
            """INSERT INTO equity_snapshots (ts, mode, total_equity, cash_balance, position_value)
               VALUES (?,?,?,?,?)""",
            (ts, mode, equity_usd, cash_usd, positions_usd),
        )
        await db.commit()


async def get_equity_snapshots(mode: str, limit: int = 500) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            "SELECT ts, total_equity, cash_balance, position_value FROM equity_snapshots WHERE mode=? ORDER BY ts ASC LIMIT ?",
            (mode, limit),
        ) as cur:
            rows = await cur.fetchall()
    return [{"ts": r[0], "equity_usd": r[1], "cash_usd": r[2], "positions_usd": r[3]} for r in rows]


# ── Settings ───────────────────────────────────────────────────────────────────

async def get_setting(key: str, default: str = "") -> str:
    async with get_db() as db:
        async with db.execute("SELECT value FROM bot_settings WHERE key=?", (key,)) as cur:
            r = await cur.fetchone()
    return r[0] if r else default


async def set_setting(key: str, value: str) -> None:
    ts = int(time.time())
    async with get_db() as db:
        await db.execute(
            "INSERT INTO bot_settings(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, ts),
        )
        await db.commit()


async def get_all_settings() -> dict:
    async with get_db() as db:
        async with db.execute("SELECT key, value FROM bot_settings") as cur:
            rows = await cur.fetchall()
    return {r[0]: r[1] for r in rows}
