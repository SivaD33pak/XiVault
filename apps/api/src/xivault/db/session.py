"""Database session and dependency provider."""

import logging
from typing import AsyncGenerator

import asyncpg

from xivault.config import settings
from xivault.db.postgres import PostgresRepository
from xivault.db.repository import BaseRepository

logger = logging.getLogger("xivault.db")

_pool: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    """Initialize connection pool directly with Supabase PostgreSQL."""
    global _pool
    db_url = settings.database_url
    if not db_url or "localhost" in db_url or "placeholder" in db_url or "USER_PROVIDED" in db_url:
        raise RuntimeError("Direct Supabase DATABASE_URL is required! Local storage fallback is disabled.")

    logger.info("Connecting to Supabase PostgreSQL at %s...", db_url.split("@")[-1])
    ssl_mode = "require" if "supabase" in db_url or "aws" in db_url else None
    _pool = await asyncpg.create_pool(
        dsn=db_url,
        min_size=1,
        max_size=10,
        ssl=ssl_mode,
        max_inactive_connection_lifetime=300.0,
        command_timeout=30.0,
    )
    logger.info("Successfully connected directly to Supabase PostgreSQL database!")


async def close_db_pool() -> None:
    """Close connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_repository() -> AsyncGenerator[BaseRepository, None]:
    """Dependency that yields the active Supabase repository."""
    if _pool is not None:
        yield PostgresRepository(_pool)
    else:
        raise RuntimeError("Supabase connection pool is not active. Local fallback is disabled.")
