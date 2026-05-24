"""FastAPI dependency injectors."""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import get_session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    sf = get_session_factory()
    async with sf() as session:
        yield session
