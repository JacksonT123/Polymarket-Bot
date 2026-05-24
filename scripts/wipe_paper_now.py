"""Wipe all paper state and reseed $1000 — no confirmation prompt."""
import asyncio
from sqlalchemy import delete
from src.db.engine import init_engine, get_session_factory
from src.db.models import Position, Signal, PositionStateLog, EquitySnapshot
from config.secrets import get_secrets
from src.core.clock import now


async def main():
    secrets = get_secrets()
    init_engine(secrets.database_url)
    sf = get_session_factory()
    async with sf() as session:
        await session.execute(delete(PositionStateLog))
        await session.execute(delete(Position))
        await session.execute(delete(Signal))
        await session.execute(delete(EquitySnapshot))
        session.add(EquitySnapshot(
            timestamp=now(),
            cash_balance=1000.0,
            position_value=0.0,
            total_equity=1000.0,
            open_position_count=0,
        ))
        await session.commit()
    print("Wiped. Reseeded at $1000.00.")

asyncio.run(main())
