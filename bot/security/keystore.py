"""
OS keychain access via `keyring`.
On Windows: Windows Credential Manager.
On macOS: Keychain Access.
On Linux: SecretService (GNOME Keyring / KWallet).

Usage:
    from bot.security.keystore import store_secret, load_secret
    store_secret("polymarket-bot-eoa-key", private_key_hex)
    pk = load_secret("polymarket-bot-eoa-key")
"""
from __future__ import annotations

import keyring
from bot.observability.log import get_logger

log = get_logger(__name__)

KEYCHAIN_SERVICE = "polymarket-bot"
_USERNAME = "polymarket-bot"


def store_secret(service: str, value: str) -> None:
    keyring.set_password(service, _USERNAME, value)
    log.info("secret_stored", service=service)


def load_secret(service: str) -> str | None:
    val = keyring.get_password(service, _USERNAME)
    if val is None:
        log.warning("secret_not_found", service=service)
    return val


def delete_secret(service: str) -> None:
    try:
        keyring.delete_password(service, _USERNAME)
        log.info("secret_deleted", service=service)
    except keyring.errors.PasswordDeleteError:
        pass


def require_secret(service: str) -> str:
    val = load_secret(service)
    if not val:
        raise RuntimeError(
            f"Required secret not found in keychain: {service}\n"
            f"Run: python -m bot.scripts.bootstrap to set up credentials."
        )
    return val
