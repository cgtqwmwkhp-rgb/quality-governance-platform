"""Database connection and session management."""

import logging
import os
import sys
import time
from typing import Any, AsyncGenerator, Optional

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from src.core.config import settings

logger = logging.getLogger(__name__)

_is_testing = "pytest" in os.environ.get("_", "") or os.environ.get("TESTING") == "1" or "pytest" in sys.modules


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


# Create async engine with conditional pooling (SQLite doesn't support pool_size)

engine_kwargs: dict[str, Any] = {
    "echo": settings.database_echo,
    "future": True,
}

if _is_testing:
    engine_kwargs["poolclass"] = NullPool
elif "postgresql" in settings.database_url:
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
            "connect_args": {
                "server_settings": {"statement_timeout": "30000"},
            },
        }
    )

engine = create_async_engine(settings.database_url, **engine_kwargs)

# Sync engine for Celery tasks
_sync_url = str(settings.database_url)
if "+asyncpg" in _sync_url:
    _sync_url = _sync_url.replace("+asyncpg", "")
elif "+aiosqlite" in _sync_url:
    _sync_url = _sync_url.replace("+aiosqlite", "")
sync_engine = create_engine(_sync_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db(request: Optional[Request] = None) -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session.

    If a tenant_id is present on request.state (set by TenantContextMiddleware),
    issues SET LOCAL on *this* connection so PostgreSQL RLS policies apply.
    """
    async with async_session_maker() as session:
        try:
            if request is not None:
                tid = getattr(request.state, "tenant_id", None)
                if tid is not None:
                    from sqlalchemy import text

                    await session.execute(
                        text("SET LOCAL app.current_tenant_id = :tid"),
                        {"tid": str(tid)},
                    )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
