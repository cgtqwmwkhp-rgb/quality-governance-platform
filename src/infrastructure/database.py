"""Database connection and session management."""

import logging
import os
import sys
import time
from typing import Any, AsyncGenerator

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from src.core.config import settings

logger = logging.getLogger(__name__)

_is_testing = (
    os.environ.get("TESTING") == "1"
    or "PYTEST_CURRENT_TEST" in os.environ
    or any("pytest" in arg for arg in sys.argv)
    or "pytest" in os.environ.get("_", "")
    or "pytest" in sys.modules
)


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
            "pool_recycle": 1800,
            "pool_timeout": 30,
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

# Pool usage tracking (async engine checkout/checkin; matches pool_size + max_overflow for PostgreSQL)
_POOL_CHECKED_OUT: int = 0
_PG_POOL_SIZE: int = 10
_PG_MAX_OVERFLOW: int = 20


def get_pool_usage_percent() -> float:
    """Return current async pool usage as a percentage (0–100), or 0 when not pooled."""
    if _is_testing or "sqlite" in settings.database_url.lower():
        return 0.0
    if "postgresql" not in settings.database_url:
        return 0.0
    capacity = _PG_POOL_SIZE + _PG_MAX_OVERFLOW
    if capacity <= 0:
        return 0.0
    return min(100.0, (_POOL_CHECKED_OUT / capacity) * 100.0)


def _register_async_pool_usage_listeners() -> None:
    """Track checked-out connections via SQLAlchemy pool events on the async engine."""

    def _on_checkout(_dbapi_conn: object, _connection_record: object, _connection_proxy: object) -> None:
        global _POOL_CHECKED_OUT
        _POOL_CHECKED_OUT += 1

    def _on_checkin(_dbapi_conn: object, _connection_record: object) -> None:
        global _POOL_CHECKED_OUT
        _POOL_CHECKED_OUT = max(0, _POOL_CHECKED_OUT - 1)

    event.listen(engine.sync_engine, "checkout", _on_checkout)
    event.listen(engine.sync_engine, "checkin", _on_checkin)


_register_async_pool_usage_listeners()


async def emit_db_pool_usage_metric() -> None:
    """Emit `db.pool_usage_percent` from the module-level checkout counter (call from a periodic task)."""
    from src.infrastructure.monitoring.azure_monitor import track_metric

    track_metric("db.pool_usage_percent", float(get_pool_usage_percent()))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        try:
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
