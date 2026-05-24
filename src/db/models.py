from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, Integer, String, Text,
    ForeignKey, JSON, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .engine import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    address: Mapped[str] = mapped_column(String(42), unique=True, nullable=False, index=True)
    alias: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="candidate", index=True)

    disqualified_reasons: Mapped[list] = mapped_column(JSON, default=list)
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_vs_category_floor_score: Mapped[float] = mapped_column(Float, default=0.0)
    closed_trades_count: Mapped[int] = mapped_column(Integer, default=0)
    months_active: Mapped[float] = mapped_column(Float, default=0.0)
    primary_category: Mapped[str] = mapped_column(String(50), default="_default")
    category_diversity_count: Mapped[int] = mapped_column(Integer, default=0)
    category_win_rate_floor: Mapped[float] = mapped_column(Float, default=0.55)
    avg_holding_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    single_market_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    volume_5min_crypto_pct: Mapped[float] = mapped_column(Float, default=0.0)
    volume_15min_crypto_pct: Mapped[float] = mapped_column(Float, default=0.0)
    positive_roi_pct: Mapped[float] = mapped_column(Float, default=0.0)
    profit_factor: Mapped[float] = mapped_column(Float, default=1.0)
    hold_to_resolution_pct: Mapped[float] = mapped_column(Float, default=0.0)
    consistency_score: Mapped[float] = mapped_column(Float, default=0.5)
    conviction_signal: Mapped[float] = mapped_column(Float, default=0.5)
    crowding_score: Mapped[float] = mapped_column(Float, default=0.0)
    crowding_score_baseline: Mapped[float] = mapped_column(Float, default=0.0)
    domain_score: Mapped[float] = mapped_column(Float, default=0.0)
    entropy_score: Mapped[float] = mapped_column(Float, default=0.0)
    insider_proximity_score: Mapped[float] = mapped_column(Float, default=0.0)
    counter_trade_signal: Mapped[float] = mapped_column(Float, default=0.0)
    is_counter_trade_candidate: Mapped[bool] = mapped_column(Boolean, default=False)

    cluster_id: Mapped[str | None] = mapped_column(String(100))
    cluster_size: Mapped[int] = mapped_column(Integer, default=1)

    last_trade_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shadow_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    shadow_copies_count: Mapped[int] = mapped_column(Integer, default=0)
    shadow_pnl_usd: Mapped[float] = mapped_column(Float, default=0.0)
    shadow_capture_ratio: Mapped[float | None] = mapped_column(Float)
    shadow_failed_cycles: Mapped[int] = mapped_column(Integer, default=0)

    consecutive_losses_for_bot: Mapped[int] = mapped_column(Integer, default=0)
    recent_capture_ratio: Mapped[float | None] = mapped_column(Float)
    suspension_count_60d: Mapped[int] = mapped_column(Integer, default=0)

    notes: Mapped[str | None] = mapped_column(Text)

    signals: Mapped[list["Signal"]] = relationship("Signal", back_populates="wallet", lazy="noload")
    positions: Mapped[list["Position"]] = relationship("Position", back_populates="wallet", lazy="noload")


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("wallets.id"), nullable=False, index=True)
    wallet_status_at_signal: Mapped[str] = mapped_column(String(20))
    market_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    token_id: Mapped[str] = mapped_column(String(100))
    side: Mapped[str] = mapped_column(String(10))
    direction: Mapped[str] = mapped_column(String(10))
    price: Mapped[float] = mapped_column(Float)
    value_usd: Mapped[float] = mapped_column(Float)
    lead_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), default="executed", index=True)
    is_shadow: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    dedup_key: Mapped[str | None] = mapped_column(String(200), index=True)

    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="signals", lazy="noload")
    position: Mapped["Position | None"] = relationship("Position", back_populates="signal", lazy="noload", uselist=False)

    __table_args__ = (
        Index("ix_signals_lead_ts_wallet", "wallet_id", "lead_timestamp"),
    )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    signal_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("signals.id"), index=True)
    wallet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("wallets.id"), nullable=False, index=True)
    market_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    token_id: Mapped[str] = mapped_column(String(100))
    side: Mapped[str] = mapped_column(String(10))
    entry_price: Mapped[float] = mapped_column(Float)
    size_shares: Mapped[float] = mapped_column(Float)
    cost_usd: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    is_shadow: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_reason: Mapped[str | None] = mapped_column(String(30))
    exit_price: Mapped[float | None] = mapped_column(Float)
    realized_pnl_usd: Mapped[float | None] = mapped_column(Float)
    unrealized_pnl_usd: Mapped[float] = mapped_column(Float, default=0.0)
    current_price: Mapped[float | None] = mapped_column(Float)

    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="positions", lazy="noload")
    signal: Mapped["Signal | None"] = relationship("Signal", back_populates="position", lazy="noload")
    state_logs: Mapped[list["PositionStateLog"]] = relationship("PositionStateLog", back_populates="position", lazy="noload")


class PositionStateLog(Base):
    __tablename__ = "position_state_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    position_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("positions.id"), nullable=False, index=True)
    from_status: Mapped[str] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(50))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    position: Mapped["Position"] = relationship("Position", back_populates="state_logs", lazy="noload")


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    cash_balance: Mapped[float] = mapped_column(Float)
    position_value: Mapped[float] = mapped_column(Float)
    total_equity: Mapped[float] = mapped_column(Float)
    open_position_count: Mapped[int] = mapped_column(Integer, default=0)
    daily_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    weekly_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    all_time_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    shadow_equity: Mapped[float] = mapped_column(Float, default=0.0)
    current_tier: Mapped[int] = mapped_column(Integer, default=0)
    rolling_7d_avg_bankroll: Mapped[float] = mapped_column(Float, default=0.0)


class TierHistory(Base):
    __tablename__ = "tier_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    from_tier: Mapped[int] = mapped_column(Integer)
    to_tier: Mapped[int] = mapped_column(Integer)
    trigger_reason: Mapped[str] = mapped_column(String(30))
    rolling_avg_at_change: Mapped[float] = mapped_column(Float)
    trade_size_new: Mapped[float] = mapped_column(Float)
    max_positions_new: Mapped[int] = mapped_column(Integer)


class WalletPerformance(Base):
    __tablename__ = "wallet_performance"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("wallets.id"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(10))   # "7d", "30d", "all"
    copies_executed: Mapped[int] = mapped_column(Integer, default=0)
    copies_won: Mapped[int] = mapped_column(Integer, default=0)
    copies_lost: Mapped[int] = mapped_column(Integer, default=0)
    copies_open: Mapped[int] = mapped_column(Integer, default=0)
    net_pnl_for_bot: Mapped[float] = mapped_column(Float, default=0.0)
    signal_to_exec_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    shadow_period: Mapped[bool] = mapped_column(Boolean, default=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (
        Index("ix_wallet_perf_wallet_period", "wallet_id", "period"),
    )


class APICallLog(Base):
    __tablename__ = "api_call_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(100))
    method: Mapped[str] = mapped_column(String(10))
    status_code: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)


class NotificationLog(Base):
    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20))
    channel: Mapped[str] = mapped_column(String(20))
    message_hash: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    delivered: Mapped[bool] = mapped_column(Boolean, default=True)
