"""PAMS external MySQL database connection (read-only).

Provides async access to the PAMS Azure MySQL database for reading
vanchecklist and vanchecklistmonthly tables.  All write operations
go to the primary QGP PostgreSQL database — PAMS is never mutated.
"""

import logging
import ssl
from typing import Any, AsyncGenerator, Optional

from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.config import settings

logger = logging.getLogger(__name__)

_pams_engine = None
_pams_session_maker: Optional[async_sessionmaker] = None
_pams_metadata: Optional[MetaData] = None
_pams_tables: dict[str, Table] = {}


def _is_configured() -> bool:
    return bool(settings.pams_database_url)


def _build_ssl_context() -> Optional[ssl.SSLContext]:
    if not settings.pams_ssl_ca:
        return None
    ctx = ssl.create_default_context(cafile=settings.pams_ssl_ca)
    return ctx


def _pymysql_ssl_args() -> dict[str, Any]:
    """Build SSL dict for pymysql (sync) connections.

    pymysql creates a bare SSLContext(PROTOCOL_TLS_CLIENT) and only loads
    the CA we specify — it does NOT load system CAs. To cover certificate
    chains that require intermediate/root CAs beyond our DigiCert bundle,
    we point to the system CA store and also include the custom CA.
    """
    import os

    if not settings.pams_ssl_ca:
        return {}
    system_ca = "/etc/ssl/certs/ca-certificates.crt"
    ca_file = system_ca if os.path.exists(system_ca) else settings.pams_ssl_ca
    return {"ssl": {"ca": ca_file}}


async def init_pams() -> None:
    """Initialise the PAMS async engine, discover table schemas."""
    global _pams_engine, _pams_session_maker, _pams_metadata

    if not _is_configured():
        logger.info("PAMS_DATABASE_URL not set — PAMS integration disabled")
        return

    connect_args: dict[str, Any] = {}
    ssl_ctx = _build_ssl_context()
    if ssl_ctx:
        connect_args["ssl"] = ssl_ctx

    _pams_engine = create_async_engine(
        settings.pams_database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
        pool_timeout=15,
        connect_args=connect_args,
    )

    _pams_session_maker = async_sessionmaker(
        _pams_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    sync_url = settings.pams_database_url.replace("+aiomysql", "+pymysql")
    sync_connect_args: dict[str, Any] = _pymysql_ssl_args()
    try:
        sync_engine = create_engine(sync_url, poolclass=NullPool, connect_args=sync_connect_args)
        _pams_metadata = MetaData()
        _pams_metadata.reflect(bind=sync_engine, only=["vanchecklist", "vanchecklistmonthly"])
        for tbl_name in ("vanchecklist", "vanchecklistmonthly"):
            if tbl_name in _pams_metadata.tables:
                _pams_tables[tbl_name] = _pams_metadata.tables[tbl_name]
                logger.info(
                    "PAMS: reflected table %s (%d columns)", tbl_name, len(_pams_metadata.tables[tbl_name].columns)
                )
            else:
                logger.warning("PAMS: table %s not found during reflection", tbl_name)
        sync_engine.dispose()
    except Exception:
        logger.exception("PAMS: schema reflection failed — endpoints will return raw dicts")


async def close_pams() -> None:
    global _pams_engine
    if _pams_engine:
        await _pams_engine.dispose()
        _pams_engine = None


async def get_pams_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for a read-only PAMS session."""
    if not _pams_session_maker:
        raise RuntimeError("PAMS database not configured")
    async with _pams_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


def get_pams_table(name: str) -> Optional[Table]:
    return _pams_tables.get(name)


def get_pams_columns(table_name: str) -> list[dict[str, str]]:
    """Return column metadata for a PAMS table."""
    tbl = _pams_tables.get(table_name)
    if not tbl:
        return []
    return [{"name": col.name, "type": str(col.type)} for col in tbl.columns]


def is_pams_available() -> bool:
    return _is_configured() and _pams_engine is not None
