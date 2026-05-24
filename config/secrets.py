from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from src.core.enums import TradingMode


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/polymarket_bot"

    # Trading
    trading_mode: TradingMode = TradingMode.PAPER
    paper_initial_balance: float = 100.0

    # Live mode credentials
    polymarket_private_key: str = ""
    polymarket_api_key: str = ""
    polymarket_api_secret: str = ""
    polymarket_api_passphrase: str = ""
    polymarket_proxy_address: str = ""

    # Notifications
    discord_webhook_url: str = ""
    ntfy_topic: str = ""

    # External data sources
    polytrack_api_key: str = ""
    polysights_api_key: str = ""

    # Dashboard
    dashboard_port: int = 8000
    dashboard_user: str = ""
    dashboard_pass: str = ""

    # Kill switch + tier override
    killswitch: int = 0
    tier_override: int | None = None

    @field_validator("tier_override", mode="before")
    @classmethod
    def parse_tier_override(cls, v: str | int | None) -> int | None:
        if v == "" or v is None:
            return None
        return int(v)

    @property
    def is_live(self) -> bool:
        return self.trading_mode == TradingMode.LIVE

    @property
    def killswitch_active(self) -> bool:
        return self.killswitch == 1


_secrets: Secrets | None = None


def get_secrets() -> Secrets:
    global _secrets
    if _secrets is None:
        _secrets = Secrets()
    return _secrets
