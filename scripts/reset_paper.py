"""Wipe all paper-mode state (positions, signals) while keeping the wallet funnel intact."""
import asyncio
from sqlalchemy import delete
from src.db.engine import init_engine, get_session_factory
from src.db.models import Position, Signal, PositionStateLog, EquitySnapshot
from config.secrets import get_secrets


async def main():
    answer = input("This will delete ALL paper positions, signals, and equity snapshots. Type 'yes' to confirm: ")
    if answer.strip().lower() != "yes":
        print("Aborted.")
        return

    secrets = get_secrets()
    init_engine(secrets.database_url)
    sf = get_session_factory()
    async with sf() as session:
        await session.execute(delete(PositionStateLog))
        await session.execute(delete(Position))
        await session.execute(delete(Signal))
        await session.execute(delete(EquitySnapshot))
        await session.commit()
    print("Paper state cleared. Wallet funnel data preserved.")


if __name__ == "__main__":
    asyncio.run(main())
