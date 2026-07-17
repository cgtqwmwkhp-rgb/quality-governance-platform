"""psycopg2 rejects asyncpg-style ssl= query params — sync URL must rewrite them."""

from src.infrastructure.database import to_sync_database_url


def test_to_sync_database_url_strips_asyncpg_and_rewrites_ssl_true():
    url = "postgresql+asyncpg://u:p@host:5432/db?ssl=true"
    out = to_sync_database_url(url)
    assert out.startswith("postgresql://u:p@host:5432/db")
    assert "ssl=" not in out
    assert "sslmode=require" in out


def test_to_sync_database_url_rewrites_ssl_require():
    out = to_sync_database_url("postgresql+asyncpg://u:p@h/db?ssl=require&application_name=qgp")
    assert "sslmode=require" in out
    assert "application_name=qgp" in out
    assert "ssl=require" not in out


def test_to_sync_database_url_keeps_existing_sslmode():
    out = to_sync_database_url("postgresql+asyncpg://u:p@h/db?ssl=true&sslmode=verify-full")
    assert "sslmode=verify-full" in out
    assert "ssl=true" not in out
    assert out.count("sslmode=") == 1


def test_to_sync_database_url_sqlite_passthrough():
    assert to_sync_database_url("sqlite+aiosqlite:///:memory:") == "sqlite:///:memory:"
