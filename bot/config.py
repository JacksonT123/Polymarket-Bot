"""
Central configuration loaded from .env via Pydantic Settings.
Private keys and API credentials live in the OS keychain (see bot/security/keystore.py).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bot.models import Mode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Mode ─────────────────────────────────────────────────────────────────
    bot_mode: Mode = Field(default=Mode.PAPER, alias="BOT_MODE")

    # ── Database ─────────────────────────────────────────────────────────────
    database_path: Path = Field(default=Path("bot.db"), alias="DATABASE_PATH")

    # ── Alchemy ───────────────────────────────────────────────────────────────
    alchemy_api_key: str = Field(default="", alias="ALCHEMY_API_KEY")

    @property
    def alchemy_http(self) -> str:
        return f"https://polygon-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}"

    @property
    def alchemy_wss(self) -> str:
        return f"wss://polygon-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}"

    # ── RPC failover ─────────────────────────────────────────────────────────
    ankr_polygon_rpc: str = Field(default="https://rpc.ankr.com/polygon", alias="ANKR_POLYGON_RPC")
    public_polygon_rpc: str = Field(default="https://polygon-rpc.com", alias="PUBLIC_POLYGON_RPC")

    # ── Optional API keys ─────────────────────────────────────────────────────
    the_graph_api_key: str = Field(default="", alias="THE_GRAPH_API_KEY")
    dune_api_key: str = Field(default="", alias="DUNE_API_KEY")
    polygonscan_api_key: str = Field(default="", alias="POLYGONSCAN_API_KEY")

    # ── Keychain service names (values stored in OS keychain, not here) ───────
    keyring_service_eoa_key: str = Field(default="polymarket-bot-eoa-key", alias="KEYRING_SERVICE_EOA_KEY")
    keyring_service_clob_api: str = Field(default="polymarket-bot-clob-api", alias="KEYRING_SERVICE_CLOB_API")
    keyring_service_clob_secret: str = Field(default="polymarket-bot-clob-secret", alias="KEYRING_SERVICE_CLOB_SECRET")
    keyring_service_clob_passphrase: str = Field(default="polymarket-bot-clob-passphrase", alias="KEYRING_SERVICE_CLOB_PASSPHRASE")

    # ── Discovery / ranking ───────────────────────────────────────────────────
    roster_active_size: int = Field(default=30, alias="ROSTER_ACTIVE_SIZE")
    roster_standby_size: int = Field(default=20, alias="ROSTER_STANDBY_SIZE")
    discovery_hour_utc: int = Field(default=4, alias="DISCOVERY_HOUR_UTC")

    # ── Wallet ────────────────────────────────────────────────────────────────
    proxy_wallet: str = Field(default="", alias="PROXY_WALLET")
    bot_eoa_address: str = Field(default="", alias="BOT_EOA_ADDRESS")

    # ── Sizing ───────────────────────────────────────────────────────────────
    base_trade_usd: float = Field(default=5.0, alias="BASE_TRADE_USD")
    min_notional_usd: float = Field(default=5.0, alias="MIN_NOTIONAL_USD")
    max_notional_usd: float = Field(default=10.0, alias="MAX_NOTIONAL_USD")

    # ── Risk ─────────────────────────────────────────────────────────────────
    max_concurrent_positions: int = Field(default=25, alias="MAX_CONCURRENT_POSITIONS")
    max_exposure_per_market_usd: float = Field(default=30.0, alias="MAX_EXPOSURE_PER_MARKET_USD")
    max_position_pct: float = Field(default=0.10, alias="MAX_POSITION_PCT")
    kill_switch_daily_loss_usd: float = Field(default=40.0, alias="KILL_SWITCH_DAILY_LOSS_USD")
    stop_loss_enabled: bool = Field(default=False, alias="STOP_LOSS_ENABLED")
    max_position_age_hours: int = Field(default=168, alias="MAX_POSITION_AGE_HOURS")

    # ── Execution ─────────────────────────────────────────────────────────────
    aggregation_window_secs: int = Field(default=120, alias="AGGREGATION_WINDOW_SECS")
    fok_tick_buffer: int = Field(default=2, alias="FOK_TICK_BUFFER")
    signal_stagger_seconds: int = Field(default=3, alias="SIGNAL_STAGGER_SECONDS")

    # ── Paper simulator ───────────────────────────────────────────────────────
    paper_pessimism_adjustment_cents: float = Field(default=0.5, alias="PAPER_PESSIMISM_ADJUSTMENT_CENTS")
    paper_depth_haircut: float = Field(default=0.25, alias="PAPER_DEPTH_HAIRCUT")
    paper_fee_rate_bps: float = Field(default=0.0, alias="PAPER_FEE_RATE_BPS")

    # ── FastAPI ───────────────────────────────────────────────────────────────
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8787, alias="API_PORT")

    # ── Chain / contracts ─────────────────────────────────────────────────────
    chain_id: int = Field(default=137, alias="CHAIN_ID")
    clob_exchange_v2: str = Field(
        default="0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
        alias="CLOB_EXCHANGE_V2",
    )
    proxy_factory: str = Field(
        default="0x56C79347e95530c01A2FC76E732f9566dA16E113",
        alias="PROXY_FACTORY",
    )
    pusdc_address: str = Field(
        default="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        alias="PUSDC_ADDRESS",
    )

    # ── Polymarket API base URLs ───────────────────────────────────────────────
    clob_base_url: str = "https://clob.polymarket.com"
    gamma_base_url: str = "https://gamma-api.polymarket.com"
    data_api_base_url: str = "https://data-api.polymarket.com"
    clob_ws_market_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    clob_ws_user_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/user"

    # ── Goldsky subgraph base ─────────────────────────────────────────────────
    goldsky_base: str = (
        "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs"
    )

    @property
    def rpc_urls(self) -> list[str]:
        urls = []
        if self.alchemy_api_key:
            urls.append(self.alchemy_http)
        urls += [self.ankr_polygon_rpc, self.public_polygon_rpc]
        return urls

    @field_validator("bot_mode", mode="before")
    @classmethod
    def coerce_mode(cls, v: str) -> Mode:
        return Mode(v.upper()) if isinstance(v, str) else v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
