import json
import time

from bot.config import get_settings
from bot.ledger.db import get_db
from bot.models import CopyIntent, DecisionCode, Leader, LeaderTradeEvent, Side


async def upsert_leaders(leaders: list[Leader], discovery_meta: dict | None = None) -> None:
    now = int(time.time())
    async with get_db() as db:
        if leaders:
            placeholders = ",".join("?" * len(leaders))
            await db.execute(
                f"DELETE FROM leaders WHERE proxy NOT IN ({placeholders})",
                [l.proxy for l in leaders],
            )
        for l in leaders:
            await db.execute(
                """INSERT OR REPLACE INTO leaders
                   (proxy, rank, score, pnl_30d, win_rate, trade_count_30d, status, cluster_id, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    l.proxy,
                    l.rank,
                    l.score,
                    l.pnl_30d,
                    l.win_rate,
                    l.trade_count_30d,
                    l.status,
                    l.cluster_id or "",
                    now,
                ),
            )
        await db.commit()


async def log_discovery_run(candidates: int, passed: int, active: int, standby: int = 0) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT INTO discovery_runs (ts, candidates, passed, active, standby) VALUES (?, ?, ?, ?, ?)",
            (int(time.time()), candidates, passed, active, standby),
        )
        await db.commit()


async def get_leaders(status: str | None = "active") -> list[dict]:
    async with get_db() as db:
        if status:
            cur = await db.execute(
                """SELECT proxy, rank, score, pnl_30d, win_rate, trade_count_30d, status, cluster_id
                   FROM leaders WHERE status = ? ORDER BY rank ASC""",
                (status,),
            )
        else:
            cur = await db.execute(
                """SELECT proxy, rank, score, pnl_30d, win_rate, trade_count_30d, status, cluster_id
                   FROM leaders ORDER BY rank ASC"""
            )
        return [dict(r) for r in await cur.fetchall()]


async def get_last_discovery() -> dict | None:
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM discovery_runs ORDER BY id DESC LIMIT 1")
        row = await cur.fetchone()
        return dict(row) if row else None


async def mark_seen(event_id: str) -> bool:
    async with get_db() as db:
        try:
            await db.execute(
                "INSERT INTO seen_events (event_id, created_at) VALUES (?, ?)",
                (event_id, int(time.time())),
            )
            await db.commit()
            return True
        except Exception:
            return False


async def log_decision(
    stage: str,
    code: DecisionCode | str,
    details: dict,
    event: LeaderTradeEvent | None = None,
) -> None:
    async with get_db() as db:
        await db.execute(
            """INSERT INTO decision_log
               (ts, stage, code, event_id, leader_proxy, condition_id, details_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                int(time.time()),
                stage,
                str(code),
                event.event_id if event else None,
                event.leader_proxy if event else None,
                event.condition_id if event else None,
                json.dumps(details),
            ),
        )
        await db.commit()


async def get_cached_bankroll(proxy: str, max_age: int) -> float | None:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT bankroll_usd, updated_at FROM leader_bankroll_cache WHERE proxy = ?",
            (proxy,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        if int(time.time()) - int(row["updated_at"]) > max_age:
            return None
        return float(row["bankroll_usd"])


async def set_cached_bankroll(proxy: str, bankroll: float) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO leader_bankroll_cache (proxy, bankroll_usd, updated_at) VALUES (?, ?, ?)",
            (proxy, bankroll, int(time.time())),
        )
        await db.commit()


async def get_account_state() -> dict:
    async with get_db() as db:
        cur = await db.execute(
            """SELECT cash_usd, equity_usd, starting_equity_usd, daily_pnl_usd,
                      kill_switch_triggered, updated_at FROM account_state WHERE id = 1"""
        )
        row = await cur.fetchone()
        return dict(row) if row else {}


async def _recalc_equity(db) -> float:
    cur = await db.execute("SELECT cash_usd FROM account_state WHERE id = 1")
    cash = float((await cur.fetchone())["cash_usd"])
    cur = await db.execute("SELECT COALESCE(SUM(shares * avg_price), 0) AS mtm FROM positions WHERE shares > 0")
    mtm = float((await cur.fetchone())["mtm"])
    equity = cash + mtm
    await db.execute(
        "UPDATE account_state SET equity_usd = ?, updated_at = ? WHERE id = 1",
        (equity, int(time.time())),
    )
    return equity


async def get_position_shares(condition_id: str, token_id: str) -> float:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT shares FROM positions WHERE condition_id = ? AND token_id = ?",
            (condition_id, token_id),
        )
        row = await cur.fetchone()
        return float(row["shares"]) if row else 0.0


async def get_position_notional(condition_id: str) -> float:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT COALESCE(SUM(shares * avg_price), 0) AS n FROM positions WHERE condition_id = ? AND shares > 0",
            (condition_id,),
        )
        return float((await cur.fetchone())["n"])


async def count_open_markets() -> int:
    async with get_db() as db:
        cur = await db.execute("SELECT COUNT(DISTINCT condition_id) AS c FROM positions WHERE shares > 0.001")
        return int((await cur.fetchone())["c"])


async def market_is_new(condition_id: str) -> bool:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT 1 FROM positions WHERE condition_id = ? AND shares > 0.001 LIMIT 1",
            (condition_id,),
        )
        return await cur.fetchone() is None


async def trigger_kill_switch(reason: str) -> None:
    async with get_db() as db:
        await db.execute("UPDATE account_state SET kill_switch_triggered = 1, updated_at = ? WHERE id = 1", (int(time.time()),))
        await db.commit()
    await log_decision("risk", DecisionCode.SKIP_KILL_SWITCH, {"reason": reason})


async def is_kill_switch_active() -> bool:
    state = await get_account_state()
    if state.get("kill_switch_triggered"):
        return True
    cfg = get_settings()
    if not cfg.kill_switch_enabled:
        return False
    starting = float(state.get("starting_equity_usd") or cfg.starting_bankroll_usd)
    equity = float(state.get("equity_usd") or 0)
    if starting - equity >= cfg.kill_switch_daily_loss_usd:
        await trigger_kill_switch("daily_loss_limit")
        return True
    return False


async def apply_fill(
    intent: CopyIntent,
    fill_price: float,
    fill_shares: float,
    *,
    mode: str,
    exchange_order_id: str = "",
) -> None:
    now = int(time.time())
    notional = fill_shares * fill_price
    async with get_db() as db:
        cur = await db.execute("SELECT cash_usd FROM account_state WHERE id = 1")
        cash = float((await cur.fetchone())["cash_usd"])

        cur_pos = await db.execute(
            "SELECT shares, avg_price FROM positions WHERE condition_id = ? AND token_id = ?",
            (intent.condition_id, intent.token_id),
        )
        row = await cur_pos.fetchone()
        held = float(row["shares"]) if row else 0.0

        pnl_delta = 0.0
        if intent.side == Side.BUY:
            new_cash = cash - notional
            if row:
                new_shares = held + fill_shares
                old_avg = float(row["avg_price"])
                new_avg = ((held * old_avg) + notional) / max(new_shares, 1e-9)
                await db.execute(
                    "UPDATE positions SET shares = ?, avg_price = ?, leader_proxy = ?, updated_at = ? WHERE condition_id = ? AND token_id = ?",
                    (new_shares, new_avg, intent.leader_proxy, now, intent.condition_id, intent.token_id),
                )
            else:
                await db.execute(
                    """INSERT INTO positions (condition_id, token_id, outcome, shares, avg_price, leader_proxy, updated_at)
                       VALUES (?, ?, '', ?, ?, ?, ?)""",
                    (intent.condition_id, intent.token_id, fill_shares, fill_price, intent.leader_proxy, now),
                )
        else:
            sell_shares = min(fill_shares, held)
            proceeds = sell_shares * fill_price
            cost_basis = sell_shares * float(row["avg_price"]) if row else 0.0
            pnl_delta = proceeds - cost_basis
            new_cash = cash + proceeds
            new_shares = max(0.0, held - sell_shares)
            if row:
                await db.execute(
                    "UPDATE positions SET shares = ?, updated_at = ? WHERE condition_id = ? AND token_id = ?",
                    (new_shares, now, intent.condition_id, intent.token_id),
                )

        await db.execute("UPDATE account_state SET cash_usd = ?, updated_at = ? WHERE id = 1", (new_cash, now))
        await _recalc_equity(db)
        await db.execute(
            """INSERT INTO fills (ts, event_id, leader_proxy, condition_id, side, shares, price, notional, mode, exchange_order_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                now,
                intent.event_id,
                intent.leader_proxy,
                intent.condition_id,
                intent.side,
                fill_shares,
                fill_price,
                notional,
                mode,
                exchange_order_id,
            ),
        )
        cur = await db.execute("SELECT realized_pnl FROM leader_pnl WHERE leader_proxy = ?", (intent.leader_proxy,))
        row_pnl = await cur.fetchone()
        prev = float(row_pnl["realized_pnl"]) if row_pnl else 0.0
        await db.execute(
            "INSERT OR REPLACE INTO leader_pnl (leader_proxy, realized_pnl, updated_at) VALUES (?, ?, ?)",
            (intent.leader_proxy, prev + pnl_delta, now),
        )
        await db.commit()

    from bot.api.broadcast import schedule_broadcast

    schedule_broadcast(force_mtm=True)


apply_paper_fill = apply_fill  # backwards compat


async def get_positions() -> list[dict]:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT condition_id, token_id, shares, avg_price, leader_proxy FROM positions WHERE shares > 0.001"
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_recent_decisions(limit: int = 200) -> list[dict]:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT ts, stage, code, event_id, leader_proxy, condition_id, details_json FROM decision_log ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        out = []
        for r in await cur.fetchall():
            d = dict(r)
            d["details"] = json.loads(d.pop("details_json"))
            out.append(d)
        return out


async def get_total_realized_pnl() -> float:
    async with get_db() as db:
        cur = await db.execute("SELECT COALESCE(SUM(realized_pnl), 0) AS t FROM leader_pnl")
        return float((await cur.fetchone())["t"])


async def get_leader_pnl() -> list[dict]:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT leader_proxy, realized_pnl FROM leader_pnl ORDER BY realized_pnl DESC"
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_leader_cursor(proxy: str) -> int | None:
    async with get_db() as db:
        cur = await db.execute("SELECT last_event_ts FROM leader_cursors WHERE proxy = ?", (proxy,))
        row = await cur.fetchone()
        return int(row["last_event_ts"]) if row else None


async def set_leader_cursor(proxy: str, last_event_ts: int) -> None:
    now = int(time.time())
    async with get_db() as db:
        await db.execute(
            """INSERT OR REPLACE INTO leader_cursors (proxy, last_event_ts, updated_at)
               VALUES (?, ?, ?)""",
            (proxy, last_event_ts, now),
        )
        await db.commit()


async def get_recent_fills(limit: int = 40) -> list[dict]:
    async with get_db() as db:
        cur = await db.execute(
            """SELECT ts, leader_proxy, condition_id, side, shares, price, notional, mode
               FROM fills ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_decision_summary(since_ts: int | None = None) -> dict:
    async with get_db() as db:
        if since_ts:
            cur = await db.execute(
                "SELECT code, COUNT(*) AS c FROM decision_log WHERE ts >= ? GROUP BY code ORDER BY c DESC",
                (since_ts,),
            )
        else:
            cur = await db.execute(
                "SELECT code, COUNT(*) AS c FROM decision_log GROUP BY code ORDER BY c DESC"
            )
        rows = await cur.fetchall()
        cur2 = await db.execute("SELECT MAX(ts) AS t FROM decision_log WHERE code = ?", (str(DecisionCode.COPIED),))
        last_copy = await cur2.fetchone()
        return {
            "by_code": {r["code"]: r["c"] for r in rows},
            "last_copy_ts": int(last_copy["t"]) if last_copy and last_copy["t"] else None,
        }


async def get_metrics() -> dict:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT code, COUNT(*) AS c FROM decision_log GROUP BY code ORDER BY c DESC"
        )
        by_code = {r["code"]: r["c"] for r in await cur.fetchall()}
        cur = await db.execute("SELECT COUNT(*) AS c FROM fills")
        fills = int((await cur.fetchone())["c"])
        return {"skip_by_code": by_code, "fills": fills}
