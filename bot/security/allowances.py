"""
Set ERC-20 allowances for the pUSD token on the CLOB V2 Exchange and CTF contracts.
Run once via `python -m bot.scripts.set_allowances` before going live.
"""
from __future__ import annotations

from web3 import AsyncWeb3

from bot.config import get_settings
from bot.observability.log import get_logger
from bot.security.keystore import require_secret

log = get_logger(__name__)

# Minimal ERC-20 ABI — approve only
_ERC20_ABI = [
    {
        "name": "approve",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "allowance",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

MAX_UINT256 = 2**256 - 1


async def set_allowances() -> None:
    cfg = get_settings()
    private_key = require_secret(cfg.keyring_service_eoa_key)

    w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(cfg.alchemy_http))
    account = w3.eth.account.from_key(private_key)
    proxy = cfg.bot_proxy_address

    pusdc = w3.eth.contract(
        address=AsyncWeb3.to_checksum_address(cfg.pusdc_address),
        abi=_ERC20_ABI,
    )

    spenders = [cfg.clob_exchange_v2]

    for spender in spenders:
        spender_cs = AsyncWeb3.to_checksum_address(spender)
        current = await pusdc.functions.allowance(proxy, spender_cs).call()
        if current >= MAX_UINT256 // 2:
            log.info("allowance_already_set", spender=spender, current=current)
            continue

        tx = await pusdc.functions.approve(spender_cs, MAX_UINT256).build_transaction(
            {
                "from": account.address,
                "nonce": await w3.eth.get_transaction_count(account.address),
                "chainId": cfg.chain_id,
            }
        )
        signed = account.sign_transaction(tx)
        tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
        log.info(
            "allowance_set",
            spender=spender,
            tx=tx_hash.hex(),
            gas_used=receipt["gasUsed"],
        )
