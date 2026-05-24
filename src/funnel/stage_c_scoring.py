"""Stage C: Compute composite score for each eligible wallet."""
import structlog
from src.metrics.win_rate import compute_win_rate_vs_category_floor
from src.metrics.profit_factor import compute_profit_factor
from src.metrics.domain_score import compute_domain_score
from src.metrics.hold_to_resolution import compute_hold_to_resolution_pct
from src.metrics.consistency import compute_consistency_score
from src.metrics.conviction import compute_conviction_signal
from src.metrics.counter_trade import compute_counter_trade_signal
from src.metrics.crowding import compute_crowding_score
from src.metrics.insider import compute_insider_proximity_score
from src.metrics.clustering import detect_cluster_size_diy
from src.metrics.entropy import compute_entropy_score
from src.metrics.composite_score import compute_composite_score

log = structlog.get_logger(__name__)


def score_wallet(wallet: dict) -> dict:
    """Computes all metrics and injects into wallet dict. Returns updated dict."""
    stats = wallet.get("stats", {})
    trades = wallet.get("trades", [])
    positions = wallet.get("positions", [])

    # Win rate vs category floor
    win_rate = stats.get("win_rate", 0.0)
    primary_cat = stats.get("primary_category", "_default")
    wr_score = compute_win_rate_vs_category_floor(win_rate, primary_cat)

    # Profit factor
    profit_factor = compute_profit_factor(trades)

    # Domain score
    cat_volume = stats.get("cat_volume", {})
    primary_cat_scored, domain_score = compute_domain_score(cat_volume)

    # Hold to resolution
    hold_pct = compute_hold_to_resolution_pct(positions)

    # Consistency
    consistency = compute_consistency_score(trades)

    # Conviction
    conviction = compute_conviction_signal(trades)

    # Counter-trade
    net_pnl = wallet.get("lifetime_pnl", 0.0)
    total_vol = stats.get("total_volume", 0.0)
    counter_signal, is_counter = compute_counter_trade_signal(net_pnl, total_vol)

    # Crowding (data stubs — real signals wired in later)
    crowding = compute_crowding_score(
        polymarket_followers=wallet.get("followers", 0),
        twitter_mentions_30d=wallet.get("twitter_mentions_30d", 0),
        appears_in_oracle_newsletter=wallet.get("in_oracle_newsletter", False),
    )

    # Insider proximity (stub — 0.0 without Polysights dataset)
    insider = compute_insider_proximity_score(trades, news_events=None)

    # Entropy
    entropy = compute_entropy_score(cat_volume)

    # Composite score
    score = compute_composite_score(
        closed_trades_count=stats.get("closed_trades_count", 0),
        win_rate_vs_category_floor_score=wr_score,
        profit_factor=profit_factor,
        months_active=stats.get("months_active", 0.0),
        domain_score=domain_score,
        hold_to_resolution_pct=hold_pct,
        consistency_score=consistency,
        conviction_signal=conviction,
        counter_trade_signal=counter_signal,
        entropy_score=entropy,
        insider_proximity_score=insider,
        max_drawdown_pct=stats.get("max_drawdown_pct", 0.0),
        crowding_score=crowding,
    )

    wallet.update({
        "composite_score": score,
        "win_rate_vs_category_floor_score": wr_score,
        "profit_factor": profit_factor,
        "primary_category": primary_cat_scored,
        "domain_score": domain_score,
        "hold_to_resolution_pct": hold_pct,
        "consistency_score": consistency,
        "conviction_signal": conviction,
        "counter_trade_signal": counter_signal,
        "is_counter_trade_candidate": is_counter,
        "crowding_score": crowding,
        "insider_proximity_score": insider,
        "entropy_score": entropy,
    })
    return wallet


def run_stage_c(eligible_wallets: list[dict]) -> list[dict]:
    """Score all eligible wallets. Returns list sorted by composite_score descending."""
    scored = [score_wallet(w) for w in eligible_wallets]
    scored.sort(key=lambda w: w.get("composite_score", 0), reverse=True)
    log.info("stage_c_complete", count=len(scored),
             top_score=scored[0]["composite_score"] if scored else 0)
    return scored
