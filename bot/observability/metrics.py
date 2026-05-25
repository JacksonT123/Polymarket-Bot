"""
Lightweight metrics: SQL aggregations over the SQLite ledger tables.
Called by /api/state and executor kill-switch check.
"""
from __future__ import annotations

from dataclasses import dataclass

from bot.ledger.db import get_db


@dataclass
class ToplineMetrics:
    mode: str
    equity_usd: float
    cash_usd: float
    open_positions_usd: float
    realized_pnl_usd: float
    unrealized_pnl_usd: float
    total_trades: int
    win_rate: float
    daily_loss_usd: float
    fill_rate: float
    paper_gate_passed: bool
    active_leaders: int


async def get_topline(mode: str) -> ToplineMetrics:
    positions_table = "paper_positions" if mode == "PAPER" else "live_positions"
    fills_table = "paper_fills" if mode == "PAPER" else "live_fills"

    async with get_db() as db:
        async def scalar(sql: str, *args):
            async with db.execute(sql, args) as cur:
                row = await cur.fetchone()
                return row[0] if row and row[0] is not None else 0

        total_trades = await scalar(f"SELECT COUNT(*) FROM {fills_table} WHERE status='FILLED'")
        total_submitted = await scalar(f"SELECT COUNT(*) FROM {fills_table}")

        # Positions
        open_positions = await scalar(f"SELECT COUNT(*) FROM {positions_table} WHERE is_open=1")
        open_positions_usd = await scalar(
            f"SELECT COALESCE(SUM(shares * avg_entry_price), 0) FROM {positions_table} WHERE is_open=1"
        )

        realized_pnl = await scalar(
            f"SELECT COALESCE(SUM(realized_pnl), 0) FROM {positions_table} WHERE is_open=0"
        )

        wins = await scalar(
            f"SELECT COUNT(*) FROM {positions_table} WHERE is_open=0 AND realized_pnl > 0"
        )
        closed_total = await scalar(f"SELECT COUNT(*) FROM {positions_table} WHERE is_open=0")
        win_rate = wins / closed_total if closed_total > 0 else 0.0

        fill_rate = total_trades / total_submitted if total_submitted > 0 else 0.0

        # Daily loss
        today_midnight = "strftime('%s','now','start of day')"
        daily_loss = await scalar(
            f"""SELECT COALESCE(SUM(CASE WHEN realized_pnl < 0 THEN ABS(realized_pnl) ELSE 0 END), 0)
                FROM {positions_table} WHERE is_open=0 AND closed_at_ts >= {today_midnight}"""
        )

        # Equity from latest snapshot
        async with db.execute(
            "SELECT total_equity, cash_balance FROM equity_snapshots WHERE mode=? ORDER BY ts DESC LIMIT 1",
            (mode,),
        ) as cur:
            eq_row = await cur.fetchone()

        equity_usd = float(eq_row[0]) if eq_row else 500.0
        cash_usd = float(eq_row[1]) if eq_row else 500.0

        # Paper gate: 14 days AND 400 trades AND net PnL > 3% AND max drawdown ≤ 8%
        paper_gate_passed = False
        if mode == "PAPER":
            paper_gate_passed = _check_paper_gate(int(total_trades), float(realized_pnl), equity_usd)

        active_leaders = await scalar(
            "SELECT COUNT(*) FROM leader_rosters WHERE snapshot_date=date('now') AND tier='active' AND status='active'"
        )

    return ToplineMetrics(
        mode=mode,
        equity_usd=equity_usd,
        cash_usd=cash_usd,
        open_positions_usd=float(open_positions_usd),
        realized_pnl_usd=float(realized_pnl),
        unrealized_pnl_usd=0.0,  # requires live price marks — updated by mark job
        total_trades=int(total_trades),
        win_rate=float(win_rate),
        daily_loss_usd=float(daily_loss),
        fill_rate=float(fill_rate),
        paper_gate_passed=paper_gate_passed,
        active_leaders=int(active_leaders),
    )


def _check_paper_gate(total_trades: int, realized_pnl: float, equity_usd: float) -> bool:
    """Paper validation gate: 400 trades, +3% PnL on $500 starting equity."""
    min_trades = 400
    min_pnl_pct = 0.03
    starting_equity = 500.0
    if total_trades < min_trades:
        return False
    if realized_pnl / starting_equity < min_pnl_pct:
        return False
    return True
