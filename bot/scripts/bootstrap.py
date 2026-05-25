"""
One-time bootstrap: initialise database, prompt for secrets, store in OS keychain.
Run once before starting the bot: `uv run python -m bot.scripts.bootstrap`
"""
from __future__ import annotations

import asyncio
import getpass
import sys

from bot.ledger.db import init_db
from bot.observability.log import configure_logging, get_logger
from bot.security.keystore import KEYCHAIN_SERVICE, load_secret, store_secret

log = get_logger(__name__)

_REQUIRED_SECRETS = [
    ("private_key", "Polygon private key (hex, no 0x prefix)"),
    ("clob_api_key", "CLOB API key"),
    ("clob_api_secret", "CLOB API secret"),
    ("clob_api_passphrase", "CLOB API passphrase"),
    ("alchemy_api_key", "Alchemy API key"),
]


async def main() -> None:
    configure_logging()
    log.info("bootstrap_start")

    # Init DB
    await init_db()
    log.info("database_initialised")

    # Check and store secrets
    print("\n=== Polymarket Bot Bootstrap ===")
    print(f"Secrets will be stored in OS keychain (service: {KEYCHAIN_SERVICE})\n")

    for key, description in _REQUIRED_SECRETS:
        existing = load_secret(key)
        if existing:
            overwrite = input(f"  '{key}' already set. Overwrite? [y/N]: ").strip().lower()
            if overwrite != "y":
                print(f"  Keeping existing '{key}'")
                continue

        value = getpass.getpass(f"  Enter {description}: ").strip()
        if not value:
            print(f"  Skipping '{key}' (empty)")
            continue

        store_secret(key, value)
        print(f"  '{key}' stored.")

    print("\n=== Bootstrap complete ===")
    print("Run: uv run python -m bot.main")
    log.info("bootstrap_complete")


if __name__ == "__main__":
    asyncio.run(main())
