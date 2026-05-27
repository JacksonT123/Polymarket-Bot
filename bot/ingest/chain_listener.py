"""
Optional faster detection via Polygon logs.
Enable with CHAIN_LISTENER_ENABLED=true and POLYGON_RPC_URL set.
Requires: pip install -e '.[chain]'
"""
from __future__ import annotations

import asyncio

from bot.config import get_settings
from bot.observability.log import get_logger

log = get_logger(__name__)

CLOB_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"


async def chain_listener_loop(stop: asyncio.Event, roster: set[str]) -> None:
    cfg = get_settings()
    if not cfg.chain_listener_enabled or not cfg.polygon_rpc_url:
        return
    try:
        from web3 import Web3
    except ImportError:
        log.warning("chain_listener_needs_web3", hint="pip install -e '.[chain]'")
        return

    w3 = Web3(Web3.HTTPProvider(cfg.polygon_rpc_url))
    if not w3.is_connected():
        log.warning("chain_rpc_not_connected")
        return

    log.info("chain_listener_started")
    last_block = w3.eth.block_number
    while not stop.is_set():
        try:
            current = w3.eth.block_number
            if current > last_block:
                last_block = current
                log.debug("chain_new_block", block=current)
            await asyncio.wait_for(stop.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            log.warning("chain_listener_error", error=str(e))
            await asyncio.sleep(5)
