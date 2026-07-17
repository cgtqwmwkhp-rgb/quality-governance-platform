"""Database connection and session management."""

import logging
import os
import sys
import time
from typing import Any, AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from src.core.config import settings
from src.domain.models.base import Base  # noqa: F401 – re-exported for metadata binding

logger = logging.getLogger(__name__)


def to_sync_database_url(database_url: str) -> str:
    """Convert an async SQLAlchemy URL into a sync driver URL safe for psycopg2.

    Azure / asyncpg DSNs often carry ``ssl=true`` (or ``ssl=require``). That is
    valid for asyncpg but rejected by libpq/psycopg2 as
    ``invalid connection option "ssl"`` — which 500'd
    ``POST /api/v1/engineers/sync-from-pams`` when it opened ``SessionLocal``.
    Rewrite ``ssl`` → ``sslmode`` for PostgreSQL URLs.
    """
    sync_url = str(database_url)
    if "+asyncpg" in sync_url:
        sync_url = sync_url.replace("+asyncpg", "")
    elif "+aiosqlite" in sync_url:
        sync_url = sync_url.replace("+aiosqlite", "")

    parts = urlsplit(sync_url)
    scheme = (parts.scheme or "").lower()
    if not (scheme.startswith("postgresql") or scheme.startswith("postgres")):
        return sync_url
    if not parts.query:
        return sync_url

    query_items = parse_qsl(parts.query, keep_blank_values=True)
    rewritten: list[tuple[str, str]] = []
    has_sslmode = any(key == "sslmode" for key, _ in query_items)
    for key, value in query_items:
        if key != "ssl":
            rewritten.append((key, value))
            continue
        if has_sslmode:
            # Prefer an explicit sslmode= already present; drop asyncpg ssl=.
            continue
        lowered = (value or "").strip().lower()
        if lowered in {"1", "true", "yes", "require"}:
            rewritten.append(("sslmode", "require"))
        elif lowered in {"0", "false", "no", "disable"}:
            rewritten.append(("sslmode", "disable"))
        elif lowered in {"prefer", "allow", "verify-ca", "verify-full"}:
            rewritten.append(("sslmode", lowered))
        else:
            rewritten.append(("sslmode", value or "require"))
        has_sslmode = True

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(rewritten), parts.fragment))

_is_testing = (
    os.environ.get("TESTING") == "1"
    or "PYTEST_CURRENT_TEST" in os.environ
    or any("pytest" in arg for arg in sys.argv)
    or "pytest" in os.environ.get("_", "")
    or "pytest" in sys.modules
)


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

# Sync engine for Celery tasks + sync-from-pams (must be psycopg2-safe)
_sync_url = to_sync_database_url(settings.database_url)
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
    """Dependency to get database session.

    When a request-scoped tenant id is present (ContextVar set by auth /
    TenantContextMiddleware), re-apply ``app.current_tenant_id`` via
    ``set_config(..., true)`` on each new transaction begin so FORCE RLS
    policies see the correct GUC on the real request session.
    """
    from sqlalchemy import text as sa_text

    from src.infrastructure.middleware.tenant_context import get_request_tenant_id

    async with async_session_maker() as session:

        def _apply_tenant_guc_after_begin(sync_session, transaction, connection) -> None:
            tenant_id = get_request_tenant_id()
            if tenant_id is None:
                return
            if connection.dialect.name != "postgresql":
                return
            connection.execute(
                sa_text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )

        event.listen(session.sync_session, "after_begin", _apply_tenant_guc_after_begin)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            event.remove(session.sync_session, "after_begin", _apply_tenant_guc_after_begin)
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
