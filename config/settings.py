# Polymarket Copy Bot v2.3 — All constants from spec. Do not edit values here;
# override via environment variables or .env file (see config/secrets.py).

# ─── Capital & Tier Ladder ──────────────────────────────────────────────────
PAPER_INITIAL_BALANCE = 100.0

# (min_bankroll, trade_size, max_positions, max_deployed_pct)
TIER_TABLE = [
    {"min_bankroll": 100,     "trade_size": 5,    "max_positions": 10, "max_deployed_pct": 0.50},
    {"min_bankroll": 250,     "trade_size": 10,   "max_positions": 12, "max_deployed_pct": 0.55},
    {"min_bankroll": 500,     "trade_size": 20,   "max_positions": 14, "max_deployed_pct": 0.60},
    {"min_bankroll": 1_000,   "trade_size": 40,   "max_positions": 16, "max_deployed_pct": 0.65},
    {"min_bankroll": 2_500,   "trade_size": 75,   "max_positions": 18, "max_deployed_pct": 0.65},
    {"min_bankroll": 5_000,   "trade_size": 150,  "max_positions": 20, "max_deployed_pct": 0.70},
    {"min_bankroll": 10_000,  "trade_size": 300,  "max_positions": 22, "max_deployed_pct": 0.70},
    {"min_bankroll": 25_000,  "trade_size": 600,  "max_positions": 24, "max_deployed_pct": 0.70},
    {"min_bankroll": 50_000,  "trade_size": 1200, "max_positions": 25, "max_deployed_pct": 0.70},
    {"min_bankroll": 100_000, "trade_size": 2000, "max_positions": 25, "max_deployed_pct": 0.70},
]

ROLLING_BANKROLL_WINDOW_DAYS     = 7
PROMOTION_GRACE_DAYS             = 7
DEMOTION_GRACE_DAYS              = 0
MAX_TIERS_PROMOTED_PER_WEEK      = 1

# ─── Wallet Funnel (v2.3) ───────────────────────────────────────────────────
CANDIDATE_POOL_SIZE              = 200
SHADOW_POOL_SIZE                 = 25
ACTIVE_POOL_SIZE                 = 5
SHADOW_MODE_MIN_DAYS             = 21
SHADOW_MIN_SIMULATED_COPIES      = 25
SHADOW_MIN_CAPTURE_RATIO         = 0.60
SHADOW_MAX_SINGLE_LOSS_PCT       = 0.15
SHADOW_MAX_FAILED_CYCLES         = 2
SHADOW_LEAD_WR_DRIFT_TOLERANCE   = 0.05

# ─── Hard Disqualifiers (13 total) ──────────────────────────────────────────
DQ_MAX_5MIN_CRYPTO_PCT           = 0.30
DQ_MAX_15MIN_CRYPTO_PCT          = 0.30
DQ_MIN_CLOSED_TRADES             = 60        # was 100
DQ_MIN_MONTHS_ACTIVE             = 2.5       # was 4 — let in newer wallets with strong edge
DQ_MAX_TRADES_PER_DAY            = 30
DQ_MIN_TRADES_PER_DAY            = 0.15      # was 0.3 — allow once-a-week specialists
DQ_MAX_SINGLE_MARKET_PNL         = 0.65      # was 0.50 — one big win is ok up to 65%
DQ_MAX_CATEGORY_DIVERSITY        = 5
DQ_MIN_AVG_HOLD_MINUTES          = 20        # was 30
DQ_MIN_WIN_RATE                  = 0.55
DQ_MAX_CLUSTER_SIZE              = 2
DQ_MIN_POSITIVE_ROI              = 0.08
DQ_MAX_DRAWDOWN_PCT              = 0.35

# ─── Category-Specific Win Rate Floors ──────────────────────────────────────
CATEGORY_WIN_RATE_FLOORS: dict[str, float] = {
    "soccer":      0.58,
    "politics":    0.60,
    "geopolitics": 0.60,
    "sports_us":   0.56,
    "weather":     0.65,
    "mention":     0.60,
    "macro":       0.60,
    "finance":     0.60,
    "crypto":      0.60,
    "culture":     0.58,
    "tech":        0.58,
    "_default":    0.55,
}

# ─── Scoring Weights (13 factors, sum positive ~1.0) ────────────────────────
W_LOG_TRADES                     = 0.10
W_WIN_RATE_VS_CATEGORY_FLOOR     = 0.18
W_LOG_PROFIT_FACTOR              = 0.15
W_MONTHS_ACTIVE                  = 0.08
W_DOMAIN_SCORE                   = 0.20
W_HOLD_TO_RESOLUTION_PCT         = 0.12
W_CONSISTENCY_SCORE              = 0.10
W_CONVICTION_SIGNAL              = 0.08
W_COUNTER_TRADE_SIGNAL           = 0.05
W_ENTROPY                        = -0.05
W_INSIDER_PROXIMITY              = -0.05
W_MAX_DRAWDOWN                   = -0.08
W_CROWDING_PENALTY               = -0.10

# ─── Active Wallet Suspension ───────────────────────────────────────────────
SUSPEND_CONSECUTIVE_LOSSES               = 3
SUSPEND_CAPTURE_RATIO_FLOOR              = 0.40
SUSPEND_CAPTURE_LOOKBACK_TRADES          = 20
SUSPEND_LEAD_SILENT_DAYS                 = 14
SUSPEND_CROWDING_SPIKE_PCT               = 0.50
PERMANENT_DROP_AFTER_N_SUSPENSIONS_IN_60D = 2

# ─── Execution Filters ──────────────────────────────────────────────────────
MIN_LEAD_TRADE_USD               = 5.0
MIN_MARKET_VOLUME_24H_USD        = 1_000.0
MIN_PRICE                        = 0.05
MAX_PRICE                        = 0.95
MAX_HOURS_TO_RESOLUTION          = 180 * 24  # 180 days in hours
MIN_HOURS_TO_RESOLUTION          = 2

# ─── Order Placement ────────────────────────────────────────────────────────
MAX_BUY_SLIPPAGE_PCT             = 0.10
MAX_SELL_SLIPPAGE_PCT            = 0.15
ORDER_RETRY_PHASES               = 3
ORDER_PHASE_1_TOLERANCE          = 0.00
ORDER_PHASE_2_TOLERANCE          = 0.02
ORDER_PHASE_3_TOLERANCE          = 0.10

# ─── Exits ──────────────────────────────────────────────────────────────────
THESIS_BROKEN_THRESHOLD          = -0.40
THESIS_BROKEN_LEAD_QUIET_H       = 24
HARD_TIME_STOP_DAYS              = 90

# ─── Circuit Breakers ───────────────────────────────────────────────────────
DAILY_LOSS_HALT_PCT              = 0.15
WEEKLY_LOSS_HALT_PCT             = 0.25
PERMANENT_HALT_DRAWDOWN_PCT      = 0.40

# ─── Risk Caps ──────────────────────────────────────────────────────────────
MAX_SAME_DAY_NEW_POSITIONS       = 5

# ─── Polling Intervals (seconds) ────────────────────────────────────────────
ACTIVITY_POLL_S                  = 5         # shadow wallet sweep interval (was 15)
ACTIVE_WALLET_POLL_S             = 2         # active wallet sweep — tighter loop
POSITION_PRICE_UPDATE_S          = 30
THESIS_BROKEN_SWEEP_S            = 30
TIME_STOP_SWEEP_S                = 6 * 3600
EQUITY_SNAPSHOT_S                = 60
WALLET_HEALTH_CHECK_S            = 86400
SHADOW_REVIEW_S                  = 86400
ACTIVE_REVIEW_S                  = 604800
CLUSTER_DETECTION_RERUN_S        = 604800

# ─── Rate Limits (requests, window_seconds) ─────────────────────────────────
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "data.leaderboard":    (1000, 10),
    "data.trades":         (200,  10),
    "data.positions":      (150,  10),
    "data.activity":       (1000, 10),
    "gamma.events":        (500,  10),
    "gamma.markets":       (300,  10),
    "gamma.general":       (4000, 10),
    "clob.read":           (1500, 10),
    "clob.post_order":     (3500, 10),
    "clob.post_order_min": (36000, 600),
}

# ─── Counter-Trade Shadow Pool ───────────────────────────────────────────────
ENABLE_COUNTER_TRADE_SHADOW      = False
COUNTER_TRADE_MIN_VOLUME_USD     = 50_000
COUNTER_TRADE_MAX_PNL_USD        = -5_000

# ─── Cache TTLs (seconds) ────────────────────────────────────────────────────
CACHE_MARKET_METADATA_TTL_S      = 300
CACHE_TOKEN_IDS_TTL_S            = 0       # 0 = indefinite

# ─── Tier-Specific Unlocks ───────────────────────────────────────────────────
# Tier 2+: loosen Filter 3 if lead trade >= this amount
TIER2_LOW_VOLUME_LEAD_MIN_USD    = 100.0
# Tier 3+: allow lead trades < MIN_LEAD_TRADE_USD on streak
TIER3_STREAK_MIN_WINS            = 5
# Tier 5+: can run 6 active wallets
TIER5_MAX_ACTIVE_WALLETS         = 6

# ─── Data Retention (days, 0 = forever) ─────────────────────────────────────
RETENTION_SIGNALS_HOT_DAYS       = 90
RETENTION_API_CALL_LOG_DAYS      = 7
RETENTION_NOTIFICATION_LOG_DAYS  = 30

# ─── Notification Dedup Window (seconds) ────────────────────────────────────
NOTIFICATION_DEDUP_WINDOW_S      = 300

# ─── Dashboard ───────────────────────────────────────────────────────────────
DASHBOARD_HOST                   = "0.0.0.0"
DASHBOARD_PORT                   = 8000
