from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings


def _fix_asyncpg_url(url: str) -> str:
    """Convert sslmode to ssl for asyncpg compatibility."""
    return url.replace("sslmode=", "ssl=")


engine = create_async_engine(_fix_asyncpg_url(settings.database_url), echo=False, poolclass=NullPool)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

