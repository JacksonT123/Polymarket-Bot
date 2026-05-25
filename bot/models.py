"""
Shared data models used across all bot modules.
Import from here to avoid circular dependencies.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Enums ─────────────────────────────────────────────────────────────────────

class Mode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class SignalStatus(str, Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    SKIPPED = "skipped"
    AGGREGATED = "aggregated"


class LeaderTier(str, Enum):
    ACTIVE = "active"
    STANDBY = "standby"


class LeaderStatus(str, Enum):
    ACTIVE = "active"
    COLD = "cold"
    PAUSED = "paused"


# ── Market / book ─────────────────────────────────────────────────────────────

@dataclass
class BookLevel:
    price: float
    size: float


@dataclass
class OrderBook:
    token_id: str
    bids: list[BookLevel]
    asks: list[BookLevel]
    market_id: str = ""
    timestamp: int = 0

    def best_ask(self) -> float | None:
        return self.asks[0].price if self.asks else None

    def best_bid(self) -> float | None:
        return self.bids[0].price if self.bids else None

    def mid(self) -> float | None:
        a, b = self.best_ask(), self.best_bid()
        if a is None or b is None:
            return None
        return (a + b) / 2


@dataclass
class MarketInfo:
    condition_id: str
    yes_token_id: str
    no_token_id: str
    question: str
    end_date_iso: str
    tick_size: float
    min_order_size: float
    active: bool
    resolved: bool


# ── Leader signals ─────────────────────────────────────────────────────────────

@dataclass
class LeaderTrade:
    """A raw trade detected from a leader wallet."""
    leader_proxy: str
    condition_id: str
    token_id: str
    outcome: str
    side: OrderSide
    price: float
    size_shares: float
    detected_at: int      # unix ts
    source: str           # "data_api" | "polygon_log"
    trade_id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class SignalEvent:
    """Normalized signal ready for aggregation."""
    proxy_address: str
    leader_rank: int
    condition_id: str
    token_id: str
    outcome: str
    side: OrderSide
    leader_price: float
    leader_size: float
    detected_ts: int
    status: SignalStatus
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    exit_reason: str | None = None


# ── Order execution ────────────────────────────────────────────────────────────

@dataclass
class OrderIntent:
    """Everything needed to execute one order."""
    condition_id: str
    token_id: str
    outcome: str
    side: OrderSide
    limit_price: float
    size_shares: float
    client_order_id: str
    signal_ids: list[str]
    leader_ranks: list[int]


@dataclass
class FillResult:
    """Result from paper simulator or live CLOB."""
    client_order_id: str
    exchange_order_id: str | None
    status: OrderStatus
    filled_shares: float
    avg_price: float
    fee_usd: float
    filled_at_ts: int
    reject_reason: str | None = None


# ── Positions ─────────────────────────────────────────────────────────────────

@dataclass
class Position:
    """An open or closed position in either ledger."""
    condition_id: str
    token_id: str
    outcome: str
    shares: float
    cost_usd: float
    avg_entry_price: float
    opened_at_ts: int
    mode: str
    signal_ids: list[str] = field(default_factory=list)
    leader_ranks: list[int] = field(default_factory=list)
    realized_pnl: float | None = None
    closed_at_ts: int | None = None
    exit_reason: str | None = None


# ── Leaders ────────────────────────────────────────────────────────────────────

@dataclass
class LeaderCandidate:
    """Raw candidate from the discovery funnel."""
    proxy_address: str
    trades_30d: int
    trade_freq: float
    win_rate: float
    realized_pnl_30d: float
    avg_position_usd: float
    per_trade_pnl: float
    per_trade_pnl_std: float
    sharpe_like: float
    market_diversity: float
    recent_7d_pnl: float
    median_hold_hours: float
    wash_score: float
    last_trade_ts: int


@dataclass
class Leader:
    """Scored, ranked leader on the active roster."""
    proxy_address: str
    rank: int
    tier: LeaderTier
    score: float
    score_delta: float
    status: LeaderStatus
    cold_since_ts: int | None
    snapshot_date: str      # YYYY-MM-DD
