from dataclasses import dataclass, field
from enum import StrEnum


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class Mode(StrEnum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class DecisionCode(StrEnum):
    COPIED = "COPIED"
    SKIP_DUPLICATE = "SKIP_DUPLICATE"
    SKIP_MIN_SIZE = "SKIP_MIN_SIZE"
    SKIP_INSUFFICIENT_CASH = "SKIP_INSUFFICIENT_CASH"
    SKIP_MARKET_LIMIT = "SKIP_MARKET_LIMIT"
    SKIP_MAX_OPEN_MARKETS = "SKIP_MAX_OPEN_MARKETS"
    SKIP_PARSE_ERROR = "SKIP_PARSE_ERROR"
    SKIP_LEADER_BANKROLL_STALE = "SKIP_LEADER_BANKROLL_STALE"
    SKIP_LEADER_BANKROLL_UNKNOWN = "SKIP_LEADER_BANKROLL_UNKNOWN"
    SKIP_KILL_SWITCH = "SKIP_KILL_SWITCH"
    SKIP_MARKET_ILLQUID = "SKIP_MARKET_ILLQUID"
    SKIP_LIVE_DISABLED = "SKIP_LIVE_DISABLED"
    SKIP_EXECUTION_ERROR = "SKIP_EXECUTION_ERROR"
    CONFLICT_NET_ZERO = "CONFLICT_NET_ZERO"
    CONFLICT_OPPOSING_SIGNALS = "CONFLICT_OPPOSING_SIGNALS"
    CONFLICT_MIN_SIZE_AFTER_NETTING = "CONFLICT_MIN_SIZE_AFTER_NETTING"
    SKIP_WALLET_UNRANKED = "SKIP_WALLET_UNRANKED"


@dataclass(slots=True)
class Leader:
    proxy: str
    rank: int
    score: float
    pnl_30d: float = 0.0
    win_rate: float = 0.0
    trade_count_30d: int = 0
    status: str = "active"
    cluster_id: str = ""


@dataclass(slots=True)
class LeaderCandidate:
    proxy: str
    pnl_30d: float = 0.0
    pnl_7d: float = 0.0
    win_rate: float = 0.0
    trade_count_30d: int = 0
    distinct_markets: int = 0
    max_drawdown: float = 0.0
    trade_freq_per_day: float = 0.0
    account_age_days: int = 0
    value_usd: float = 0.0
    wash_score: float = 0.0
    score: float = 0.0
    exclude_reason: str | None = None


@dataclass(slots=True)
class LeaderTradeEvent:
    event_id: str
    leader_proxy: str
    condition_id: str
    token_id: str
    side: Side
    price: float
    usdc_size: float
    timestamp: int
    tx_hash: str
    outcome: str = ""


@dataclass(slots=True)
class CopyIntent:
    event_id: str
    leader_proxy: str
    condition_id: str
    token_id: str
    side: Side
    target_notional: float
    target_shares: float
    limit_price: float
    leader_fraction: float = 0.0
    sizing_details: dict = field(default_factory=dict)


@dataclass(slots=True)
class BankrollSnapshot:
    proxy: str
    bankroll_usd: float
    updated_at: int
    stale: bool = False
