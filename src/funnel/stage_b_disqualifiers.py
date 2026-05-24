"""Stage B: Apply 13 hard disqualifiers. Returns list of (address, reasons) for DQ'd wallets."""
from datetime import datetime, timezone
from collections import defaultdict
from typing import Any
import structlog

from config.settings import (
    DQ_MAX_5MIN_CRYPTO_PCT, DQ_MAX_15MIN_CRYPTO_PCT, DQ_MIN_CLOSED_TRADES,
    DQ_MIN_MONTHS_ACTIVE, DQ_MAX_TRADES_PER_DAY, DQ_MIN_TRADES_PER_DAY,
    DQ_MAX_SINGLE_MARKET_PNL, DQ_MAX_CATEGORY_DIVERSITY, DQ_MIN_AVG_HOLD_MINUTES,
    DQ_MIN_WIN_RATE, DQ_MAX_CLUSTER_SIZE, DQ_MIN_POSITIVE_ROI, DQ_MAX_DRAWDOWN_PCT,
    CATEGORY_WIN_RATE_FLOORS,
)

log = structlog.get_logger(__name__)


def _parse_ts(val) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, tz=timezone.utc)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _trade_usd(t: dict) -> float:
    """Best-effort USD size from a trade record (real API uses 'amount')."""
    for field in ("amount", "size_usd", "usdcAmount", "usdc"):
        v = t.get(field)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    # fallback: size (shares) * price
    size = t.get("size", 0) or 0
    price = t.get("price", 0) or 0
    return float(size) * float(price)


def _position_pnl(pos: dict) -> float | None:
    """Extract PNL from a position record."""
    for field in ("pnl", "cashEarned", "realized", "realizedPnl", "profit"):
        v = pos.get(field)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    # compute from value fields
    initial = pos.get("initialValue") or pos.get("cost") or pos.get("investedAmount")
    current = pos.get("currentValue") or pos.get("value") or pos.get("redeemable")
    if initial is not None and current is not None:
        try:
            return float(current) - float(initial)
        except (TypeError, ValueError):
            pass
    return None


def _is_position_resolved(pos: dict) -> bool:
    """Return True if the position's market has resolved."""
    if pos.get("resolved") or pos.get("closed") or pos.get("redeemed"):
        return True
    status = (pos.get("status") or "").upper()
    if status in ("RESOLVED", "REDEEMED", "CLOSED"):
        return True
    market = pos.get("market") or {}
    if isinstance(market, dict):
        if market.get("resolved") or market.get("closed"):
            return True
    return False


def compute_stats(wallet: dict) -> dict[str, Any]:
    """Pre-compute all stats needed for disqualifier checks from raw trade/position data."""
    trades: list[dict] = wallet.get("trades", [])
    positions: list[dict] = wallet.get("positions", [])

    # All executed trades count as "closed" (they are matched fills)
    closed = trades

    # Resolved positions are used for win-rate and PNL analysis
    resolved_positions = [p for p in positions if _is_position_resolved(p)]

    # If no trades or positions at all, return empty
    if not trades and not positions:
        return {}

    # Date range for trades per day (use any timestamp field)
    timestamps = []
    for t in trades:
        ts_raw = t.get("timestamp") or t.get("matchTime") or t.get("created_at") or t.get("createTime")
        ts = _parse_ts(ts_raw)
        if ts:
            timestamps.append(ts)
    if timestamps:
        earliest = min(timestamps)
        days_active = max(1, (datetime.now(timezone.utc) - earliest).days)
        months_active = days_active / 30.44
    else:
        days_active = 1
        months_active = 0

    trades_per_day = len(trades) / days_active

    # Category breakdown by USD volume (real API uses 'amount' not 'size_usd')
    cat_volume: dict[str, float] = defaultdict(float)
    for t in trades:
        cat = t.get("category", "_default") or "_default"
        cat_volume[cat] += _trade_usd(t)
    total_vol = sum(cat_volume.values()) or 1

    # 5-min / 15-min crypto volume
    crypto_5m = sum(v for k, v in cat_volume.items() if "5m" in k.lower() or "5min" in k.lower())
    crypto_15m = sum(v for k, v in cat_volume.items() if "15m" in k.lower() or "15min" in k.lower())

    # Win rate: reconstruct from trades using net PNL per (conditionId, outcome) pair.
    # The positions endpoint only shows open positions; trades are the only historical record.
    # Group by (conditionId, outcome): total bought/sold shares + value to determine if trade was profitable.
    market_books: dict[tuple, dict] = defaultdict(lambda: {"bought": 0.0, "sold": 0.0, "buy_val": 0.0, "sell_val": 0.0})
    for t in trades:
        key = (t.get("conditionId", ""), t.get("outcome", ""))
        size = float(t.get("size", 0) or 0)
        price = float(t.get("price", 0) or 0)
        val = size * price
        if t.get("side", "").upper() == "BUY":
            market_books[key]["bought"] += size
            market_books[key]["buy_val"] += val
        else:
            market_books[key]["sold"] += size
            market_books[key]["sell_val"] += val

    wins = 0
    market_pnl: dict[str, float] = defaultdict(float)
    resolved_market_count = 0
    for (cid, outcome), book in market_books.items():
        if book["bought"] <= 0:
            continue
        exit_pct = book["sold"] / book["bought"]
        pnl = book["sell_val"] - book["buy_val"]
        if exit_pct >= 0.8:
            # Fully exited — realize PNL
            resolved_market_count += 1
            if pnl > 0:
                wins += 1
            market_pnl[cid] += pnl
        elif book["sell_val"] > 0 and book["sell_val"] / book["buy_val"] > 1:
            # Partial exit at profit → count as win
            resolved_market_count += 1
            wins += 1
            market_pnl[cid] += pnl

    win_rate = wins / resolved_market_count if resolved_market_count > 0 else 0.0
    total_pnl = sum(abs(v) for v in market_pnl.values()) or 1
    max_market_pnl_pct = max((abs(v) / total_pnl for v in market_pnl.values()), default=0)

    # Holding time: estimated from first vs last trade per conditionId
    market_ts: dict[str, list[datetime]] = defaultdict(list)
    for t in trades:
        ts = _parse_ts(t.get("timestamp") or t.get("matchTime"))
        if ts:
            market_ts[t.get("conditionId", "")].append(ts)
    holding_minutes: list[float] = []
    for ts_list in market_ts.values():
        if len(ts_list) >= 2:
            mins = (max(ts_list) - min(ts_list)).total_seconds() / 60
            if mins > 0:
                holding_minutes.append(mins)
    avg_holding_minutes = sum(holding_minutes) / len(holding_minutes) if holding_minutes else 0

    # Positive ROI from winning markets
    rois = []
    for (cid, outcome), book in market_books.items():
        if book["bought"] <= 0:
            continue
        exit_pct = book["sold"] / book["bought"]
        if exit_pct >= 0.8:
            pnl = book["sell_val"] - book["buy_val"]
            if pnl > 0 and book["buy_val"] > 0:
                rois.append(pnl / book["buy_val"])
    positive_roi = sum(rois) / len(rois) if rois else 0

    # Max drawdown from per-day PNL of resolved markets
    pnl_by_day: dict[str, float] = defaultdict(float)
    for t in trades:
        if t.get("side", "").upper() == "SELL":
            ts = _parse_ts(t.get("timestamp") or t.get("matchTime"))
            if ts:
                pnl_by_day[str(ts.date())] += float(t.get("size", 0) or 0) * float(t.get("price", 0) or 0)
    cumulative, peak, max_dd = 0.0, 0.0, 0.0
    for v in sorted(pnl_by_day.items()):
        cumulative += v[1]
        if cumulative > peak:
            peak = cumulative
        if peak > 0:
            dd = (peak - cumulative) / peak
            max_dd = max(max_dd, dd)

    # Primary category
    primary_cat = max(cat_volume, key=lambda k: cat_volume[k]) if cat_volume else "_default"
    category_floor = CATEGORY_WIN_RATE_FLOORS.get(primary_cat, CATEGORY_WIN_RATE_FLOORS["_default"])

    lb_trades_count = int(wallet.get("lb_trades_count", 0) or 0)
    effective_closed = max(len(closed), lb_trades_count)
    # If we couldn't reconstruct enough resolved trades, skip win rate DQ (insufficient data)
    effective_win_rate = win_rate if resolved_market_count >= 10 else None

    return {
        "closed_trades_count": effective_closed,
        "resolved_trades_count": resolved_market_count,
        "months_active": months_active,
        "trades_per_day": trades_per_day,
        "volume_5min_crypto_pct": crypto_5m / total_vol,
        "volume_15min_crypto_pct": crypto_15m / total_vol,
        "single_market_pnl_pct": max_market_pnl_pct,
        "category_diversity_count": len(cat_volume),
        "avg_holding_minutes": avg_holding_minutes,
        "win_rate": effective_win_rate,  # None means insufficient data to evaluate
        "category_floor": category_floor,
        "primary_category": primary_cat,
        "positive_roi_pct": positive_roi,
        "max_drawdown_pct": max_dd,
        "cat_volume": dict(cat_volume),
        "total_volume": total_vol,
    }


def apply_disqualifiers(wallet: dict, stats: dict, cluster_size: int = 1) -> list[str]:
    """Returns list of DQ reason strings. Empty list = ELIGIBLE."""
    reasons: list[str] = []

    if not stats:
        reasons.append("no_trade_data")
        return reasons

    if stats["volume_5min_crypto_pct"] > DQ_MAX_5MIN_CRYPTO_PCT:
        reasons.append(f"hft_5min_crypto:{stats['volume_5min_crypto_pct']:.2%}")
    if stats["volume_15min_crypto_pct"] > DQ_MAX_15MIN_CRYPTO_PCT:
        reasons.append(f"hft_15min_crypto:{stats['volume_15min_crypto_pct']:.2%}")
    if stats["closed_trades_count"] < DQ_MIN_CLOSED_TRADES:
        reasons.append(f"insufficient_trades:{stats['closed_trades_count']}")
    if stats["months_active"] < DQ_MIN_MONTHS_ACTIVE:
        reasons.append(f"insufficient_track_record:{stats['months_active']:.1f}mo")
    if stats["trades_per_day"] > DQ_MAX_TRADES_PER_DAY:
        reasons.append(f"too_many_trades_per_day:{stats['trades_per_day']:.1f}")
    if stats["trades_per_day"] < DQ_MIN_TRADES_PER_DAY:
        reasons.append(f"too_few_trades_per_day:{stats['trades_per_day']:.3f}")
    if stats["single_market_pnl_pct"] > DQ_MAX_SINGLE_MARKET_PNL:
        reasons.append(f"one_shot_concentration:{stats['single_market_pnl_pct']:.2%}")
    if stats["category_diversity_count"] > DQ_MAX_CATEGORY_DIVERSITY:
        reasons.append(f"too_diverse:{stats['category_diversity_count']}_cats")
    if stats["avg_holding_minutes"] < DQ_MIN_AVG_HOLD_MINUTES and stats["avg_holding_minutes"] > 0:
        reasons.append(f"too_short_holds:{stats['avg_holding_minutes']:.0f}min")
    if stats["win_rate"] is not None:
        effective_floor = max(stats["category_floor"], DQ_MIN_WIN_RATE)
        if stats["win_rate"] < effective_floor:
            reasons.append(f"below_win_rate_floor:{stats['win_rate']:.2%}_<_{effective_floor:.2%}")
    if cluster_size > DQ_MAX_CLUSTER_SIZE:
        reasons.append(f"cluster_too_large:{cluster_size}")
    if stats["positive_roi_pct"] < DQ_MIN_POSITIVE_ROI and stats["resolved_trades_count"] > 10:
        reasons.append(f"roi_below_floor:{stats['positive_roi_pct']:.2%}")
    if stats["max_drawdown_pct"] > DQ_MAX_DRAWDOWN_PCT:
        reasons.append(f"max_drawdown_too_high:{stats['max_drawdown_pct']:.2%}")

    return reasons


def run_stage_b(candidates: list[dict], cluster_sizes: dict[str, int] | None = None) -> tuple[list[dict], list[dict]]:
    """
    Returns (eligible_wallets, disqualified_wallets).
    Each dict has wallet data + injected 'stats' and 'dq_reasons'.
    """
    eligible, disqualified = [], []
    for wallet in candidates:
        stats = compute_stats(wallet)
        cluster_size = (cluster_sizes or {}).get(wallet["address"], 1)
        reasons = apply_disqualifiers(wallet, stats, cluster_size)
        wallet["stats"] = stats
        wallet["dq_reasons"] = reasons
        if reasons:
            disqualified.append(wallet)
        else:
            eligible.append(wallet)

    log.info("stage_b_complete",
             eligible=len(eligible),
             disqualified=len(disqualified),
             top_dq_reasons=_tally_reasons(disqualified))
    return eligible, disqualified


def _tally_reasons(disqualified: list[dict]) -> dict[str, int]:
    tally: dict[str, int] = defaultdict(int)
    for w in disqualified:
        for r in w.get("dq_reasons", []):
            key = r.split(":")[0]
            tally[key] += 1
    return dict(sorted(tally.items(), key=lambda x: -x[1])[:5])
