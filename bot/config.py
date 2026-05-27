from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    bot_mode: str = Field(default="PAPER", alias="BOT_MODE")
    database_path: Path = Field(default=Path("bot.db"), alias="DATABASE_PATH")
    data_api_base_url: str = Field(default="https://data-api.polymarket.com", alias="DATA_API_BASE_URL")
    clob_base_url: str = Field(default="https://clob.polymarket.com", alias="CLOB_BASE_URL")
    gamma_base_url: str = Field(default="https://gamma-api.polymarket.com", alias="GAMMA_BASE_URL")

    tracked_wallets: str = Field(default="", alias="TRACKED_WALLETS")
    auto_discover_leaders: bool = Field(default=True, alias="AUTO_DISCOVER_LEADERS")

    roster_active_size: int = Field(default=15, alias="ROSTER_ACTIVE_SIZE")
    roster_standby_size: int = Field(default=30, alias="ROSTER_STANDBY_SIZE")
    roster_churn_pct: float = Field(default=0.10, alias="ROSTER_CHURN_PCT")
    discovery_interval_hours: float = Field(default=6.0, alias="DISCOVERY_INTERVAL_HOURS")
    discovery_leaderboard_limit: int = Field(default=100, alias="DISCOVERY_LEADERBOARD_LIMIT")

    activity_poll_seconds: float = Field(default=6.0, alias="ACTIVITY_POLL_SECONDS")
    activity_concurrency: int = Field(default=1, alias="ACTIVITY_CONCURRENCY")
    data_api_min_interval_ms: int = Field(default=450, alias="DATA_API_MIN_INTERVAL_MS")
    clob_min_interval_ms: int = Field(default=200, alias="CLOB_MIN_INTERVAL_MS")
    mtm_cache_seconds: float = Field(default=2.0, alias="MTM_CACHE_SECONDS")
    dashboard_ws_interval_ms: int = Field(default=500, alias="DASHBOARD_WS_INTERVAL_MS")
    bankroll_cache_seconds: int = Field(default=600, alias="BANKROLL_CACHE_SECONDS")
    bankroll_stale_seconds: int = Field(default=1800, alias="BANKROLL_STALE_SECONDS")
    conflict_window_seconds: int = Field(default=60, alias="CONFLICT_WINDOW_SECONDS")

    starting_bankroll_usd: float = Field(default=100.0, alias="STARTING_BANKROLL_USD")
    min_copy_usd: float = Field(default=1.0, alias="MIN_COPY_USD")
    min_copy_usd_live: float = Field(default=2.0, alias="MIN_COPY_USD_LIVE")
    max_copy_pct_per_trade: float = Field(default=0.05, alias="MAX_COPY_PCT_PER_TRADE")
    max_leader_fraction_per_trade: float = Field(default=0.25, alias="MAX_LEADER_FRACTION_PER_TRADE")
    max_copy_pct_per_market: float = Field(default=0.20, alias="MAX_COPY_PCT_PER_MARKET")
    max_open_markets: int = Field(default=8, alias="MAX_OPEN_MARKETS")

    kill_switch_daily_loss_usd: float = Field(default=40.0, alias="KILL_SWITCH_DAILY_LOSS_USD")
    kill_switch_enabled: bool = Field(default=False, alias="KILL_SWITCH_ENABLED")

    paper_slippage_cents: float = Field(default=0.2, alias="PAPER_SLIPPAGE_CENTS")
    paper_depth_haircut: float = Field(default=0.25, alias="PAPER_DEPTH_HAIRCUT")
    order_type: str = Field(default="FAK", alias="ORDER_TYPE")

    ssl_verify: bool = Field(default=False, alias="SSL_VERIFY")

    # Live — same execution path; set BOT_MODE=LIVE + fill credentials
    polygon_private_key: str = Field(default="", alias="POLYGON_PRIVATE_KEY")
    polymarket_proxy_address: str = Field(default="", alias="POLYMARKET_PROXY_ADDRESS")
    clob_api_key: str = Field(default="", alias="CLOB_API_KEY")
    clob_api_secret: str = Field(default="", alias="CLOB_API_SECRET")
    clob_api_passphrase: str = Field(default="", alias="CLOB_API_PASSPHRASE")
    signature_type: int = Field(default=1, alias="SIGNATURE_TYPE")
    chain_id: int = Field(default=137, alias="CHAIN_ID")

    polygon_rpc_url: str = Field(default="", alias="POLYGON_RPC_URL")
    chain_listener_enabled: bool = Field(default=False, alias="CHAIN_LISTENER_ENABLED")

    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8787, alias="API_PORT")

    @property
    def is_live(self) -> bool:
        return self.bot_mode.upper() == "LIVE"

    @property
    def min_copy_for_mode(self) -> float:
        return self.min_copy_usd_live if self.is_live else self.min_copy_usd

    @property
    def live_ready(self) -> bool:
        return bool(self.polygon_private_key and self.polymarket_proxy_address)


@lru_cache
def get_settings() -> Settings:
    return Settings()
