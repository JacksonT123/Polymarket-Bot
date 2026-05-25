"""
Derive your proxy wallet address from the private key in OS keychain.
Run: `uv run python -m bot.scripts.derive_proxy`
"""
from __future__ import annotations

import asyncio

from eth_account import Account

from bot.observability.log import configure_logging, get_logger
from bot.security.keystore import require_secret

log = get_logger(__name__)


async def main() -> None:
    configure_logging()
    private_key = require_secret("private_key")
    account = Account.from_key(private_key)
    print(f"\nEOA address:   {account.address}")
    print("\nTo find your proxy wallet, visit:")
    print(f"  https://polymarket.com/profile/{account.address}")
    print("\nSet PROXY_WALLET in your .env to the proxy address shown on that page.")


if __name__ == "__main__":
    asyncio.run(main())
