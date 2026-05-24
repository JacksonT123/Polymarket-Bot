from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, Field
from .enums import (
    WalletStatus, SignalDirection, SignalOutcome,
    PositionStatus, ExitReason, TradingMode,
)


class WalletRecord(BaseModel):
    address: str
    alias: str | None = None
    status: WalletStatus = WalletStatus.CANDIDATE

    # Core stats
    win_rate: float = 0.0
    closed_trades_count: int = 0
    months_active: float = 0.0
    primary_category: str = "_default"
    category_diversity_count: int = 0
    category_win_rate_floor: float = 0.55
    avg_holding_minutes: float = 0.0
    max_drawdown_pct: float = 0.0
    single_market_pnl_pct: float = 0.0
    volume_5min_crypto_pct: float = 0.0
    volume_15min_crypto_pct: float = 0.0
    positive_roi_pct: float = 0.0
    profit_factor: float = 1.0

    # v2.3 metrics
    hold_to_resolution_pct: float = 0.0
    consistency_score: float = 0.5
    conviction_signal: float = 0.5
    crowding_score: float = 0.0
    crowding_score_baseline: float = 0.0
    domain_score: float = 0.0
    entropy_score: float = 0.0
    insider_proximity_score: float = 0.0
    counter_trade_signal: float = 0.0
    is_counter_trade_candidate: bool = False

    # Cluster
    cluster_id: str | None = None
    cluster_size: int = 1

    # Composite score (computed)
    composite_score: float = 0.0
    win_rate_vs_category_floor_score: float = 0.0

    # Shadow tracking
    shadow_started_at: datetime | None = None
    shadow_copies_count: int = 0
    shadow_pnl_usd: float = 0.0
    shadow_capture_ratio: float | None = None
    shadow_failed_cycles: int = 0

    # Active tracking
    activated_at: datetime | None = None
    suspended_at: datetime | None = None
    last_trade_at: datetime | None = None
    consecutive_losses_for_bot: int = 0
    recent_capture_ratio: float | None = None
    suspension_count_60d: int = 0

    disqualified_reasons: list[str] = Field(default_factory=list)
    notes: str | None = None


class MarketMetadata(BaseModel):
    condition_id: str
    question: str
    category: str = "_default"
    volume_24h_usd: float = 0.0
    end_date: datetime | None = None
    is_closed: bool = False
    yes_token_id: str = ""
    no_token_id: str = ""


class SignalEvent(BaseModel):
    wallet_address: str
    market_id: str
    token_id: str
    side: str  # "YES" or "NO"
    direction: SignalDirection
    price: float
    value_usd: float
    lead_timestamp: datetime
    detected_at: datetime
    is_shadow: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class FilterResult(BaseModel):
    passed: bool
    reason: SignalOutcome | None = None
    detail: str | None = None


class TradeParams(BaseModel):
    tier: int
    trade_size_usd: float
    max_positions: int
    max_deployed_pct: float


class FillResult(BaseModel):
    success: bool
    fill_price: float
    fill_size_shares: float
    cost_usd: float
    slippage_pct: float
    fee_usd: float
    phase_used: str | None = None
    error: str | None = None


class PositionRecord(BaseModel):
    id: int | None = None
    signal_id: int | None = None
    wallet_address: str
    market_id: str
    token_id: str
    side: str
    entry_price: float
    size_shares: float
    cost_usd: float
    status: PositionStatus = PositionStatus.OPEN
    is_shadow: bool = False
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    exit_reason: ExitReason | None = None
    exit_price: float | None = None
    realized_pnl_usd: float | None = None
    unrealized_pnl_usd: float = 0.0
    current_price: float | None = None


class EquitySnapshot(BaseModel):
    timestamp: datetime
    cash_balance: float
    position_value: float
    total_equity: float
    open_position_count: int
    daily_pnl: float
    weekly_pnl: float
    all_time_pnl: float
    shadow_equity: float = 0.0
    current_tier: int = 0
    rolling_7d_avg_bankroll: float = 0.0


class DailyReport(BaseModel):
    date: str
    mode: TradingMode
    equity: float
    equity_pct_change: float
    tier: int
    trade_size_usd: float
    open_positions: int
    deployed_usd: float
    deployed_pct: float
    max_deployed_pct: float
    executed_today: int
    skipped_today: int
    closed_today: int
    pnl_today: float
    active_wallet_count: int
    shadow_wallet_count: int
    signal_exec_ratio: float
    circuit_breakers_clear: bool
