from __future__ import annotations

import ssl as _ssl
from collections.abc import AsyncGenerator
from urllib.parse import urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings


def _make_engine():
    """Create async engine with proper SSL handling for asyncpg."""
    url = settings.database_url

    # For asyncpg (postgresql+asyncpg://), strip query params that asyncpg
    # doesn't understand (sslmode, channel_binding, etc.) and pass SSL
    # config via connect_args instead.
    connect_args = {}
    if "asyncpg" in url:
        parsed = urlparse(url)
        needs_ssl = "sslmode=require" in (parsed.query or "")
        clean_url = urlunparse(parsed._replace(query=""))
        url = clean_url
        if needs_ssl:
            ssl_ctx = _ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = _ssl.CERT_NONE
            connect_args["ssl"] = ssl_ctx
        
        # Add timeout to asyncpg
        connect_args["command_timeout"] = 60
        connect_args["timeout"] = 60

    # Common engine arguments
    engine_args = {
        "echo": False,
        "connect_args": connect_args
    }

    # Only add pooling arguments for non-SQLite databases (like PostgreSQL)
    if "sqlite" not in url:
        engine_args.update({
            "pool_size": 5,
            "max_overflow": 10,
            "pool_recycle": 300,
            "pool_pre_ping": True,
        })

    return create_async_engine(url, **engine_args)


engine = _make_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

