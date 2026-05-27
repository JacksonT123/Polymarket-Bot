import uvicorn

from bot.api.server import app
from bot.config import get_settings
from bot.observability.log import configure_logging


def cli() -> None:
    configure_logging()
    cfg = get_settings()
    uvicorn.run(app, host=cfg.api_host, port=cfg.api_port, log_level="info")


if __name__ == "__main__":
    cli()
