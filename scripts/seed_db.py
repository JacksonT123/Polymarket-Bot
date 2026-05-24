"""Initialize a fresh DB with a starting equity snapshot."""
import asyncio
from datetime import datetime, timezone
from src.db.engine import init_engine, get_session_factory
from src.db.models import EquitySnapshot
from config.secrets import get_secrets


async def main():
    secrets = get_secrets()
    init_engine(secrets.database_url)
    sf = get_session_factory()
    async with sf() as session:
        snap = EquitySnapshot(
            timestamp=datetime.now(timezone.utc),
            cash_balance=1000.0,
            position_value=0.0,
            total_equity=1000.0,
            open_position_count=0,
        )
        session.add(snap)
        await session.commit()
    print("DB seeded with $1000.00 starting equity.")


if __name__ == "__main__":
    asyncio.run(main())
