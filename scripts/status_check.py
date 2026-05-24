import asyncio
from src.db.engine import init_engine, get_session_factory
from src.db.models import Wallet, Position
from src.core.enums import WalletStatus
from sqlalchemy import select, func
from config.secrets import get_secrets


async def main():
    secrets = get_secrets()
    init_engine(secrets.database_url)
    sf = get_session_factory()
    async with sf() as session:
        active = await session.scalar(select(func.count()).where(Wallet.status == WalletStatus.ACTIVE.value))
        shadow = await session.scalar(select(func.count()).where(Wallet.status == WalletStatus.SHADOW.value))
        total_pos = await session.scalar(select(func.count()).select_from(Position))
        open_pos = await session.scalar(select(func.count()).select_from(Position).where(Position.status == "open"))
        pending_pos = await session.scalar(select(func.count()).select_from(Position).where(Position.status == "pending"))
        print(f"Active wallets:  {active}")
        print(f"Shadow wallets:  {shadow}")
        print(f"Total positions: {total_pos}")
        print(f"Open positions:  {open_pos}")
        print(f"Pending positions: {pending_pos}")

asyncio.run(main())
