"""Regression tests for the test-database safety guard.

The guard exists because ``tests/integration/conftest.py`` uses
``os.environ.setdefault("DATABASE_URL", ...)``: an exported DSN wins over the
harness default, and the suite then seeds and writes to whatever it points at.
"""

from __future__ import annotations

import pytest

from tests._dsn_guard import UnsafeTestDatabaseError, assert_test_database_is_local


class TestRejectsNonLocalDatabases:
    def test_rejects_azure_postgres(self):
        """The exact shape of DSN that was live in the shell during Run021."""
        with pytest.raises(UnsafeTestDatabaseError) as exc:
            assert_test_database_is_local(
                "postgresql+asyncpg://qgpadmin:secret@psql-qgp-prod.postgres.database.azure.com:5432/qgp_prod_live"
            )
        assert "psql-qgp-prod.postgres.database.azure.com" in str(exc.value)

    def test_rejects_staging_too(self):
        """Staging is a real deployment with real data; it is not a test database."""
        with pytest.raises(UnsafeTestDatabaseError):
            assert_test_database_is_local(
                "postgresql+asyncpg://u:p@psql-qgp-staging.postgres.database.azure.com/qgp_staging"
            )

    def test_rejects_arbitrary_remote_host(self):
        """Allow-list, not deny-list: an unknown host is refused by default."""
        with pytest.raises(UnsafeTestDatabaseError):
            assert_test_database_is_local("postgresql+asyncpg://u:p@db.example.net:5432/anything")

    def test_rejects_unparseable_dsn(self):
        """A DSN we cannot read is not demonstrably local, so it is not allowed."""
        with pytest.raises(UnsafeTestDatabaseError):
            assert_test_database_is_local("postgresql+asyncpg://u:p@[unclosed:5432/db")


class TestAllowsLegitimateTestDatabases:
    @pytest.mark.parametrize(
        "dsn",
        [
            "sqlite+aiosqlite:///./test.db",
            "sqlite:///:memory:",
            "sqlite+aiosqlite:////tmp/qgp-test-integration-123.db",
        ],
    )
    def test_allows_sqlite(self, dsn):
        assert_test_database_is_local(dsn)

    @pytest.mark.parametrize(
        "dsn",
        [
            # Exactly what every Postgres job in .github/workflows/ci.yml sets.
            "postgresql+asyncpg://postgres:testpass@localhost:5432/quality_governance_test",
            "postgresql+asyncpg://postgres:testpass@127.0.0.1:5432/quality_governance_test",
            "postgresql://postgres:testpass@db:5432/test",
        ],
    )
    def test_allows_local_postgres(self, dsn):
        assert_test_database_is_local(dsn)

    def test_allows_unset_dsn(self):
        """No DSN means the harness falls back to its own temporary SQLite file."""
        assert_test_database_is_local("")


class TestOverride:
    def test_override_permits_remote_but_warns(self, monkeypatch, capsys):
        monkeypatch.setenv("QGP_I_UNDERSTAND_TESTS_WILL_WRITE_TO_THIS_DATABASE", "1")
        assert_test_database_is_local("postgresql+asyncpg://u:p@db.example.net/x")
        assert "safety guard is disabled" in capsys.readouterr().err

    def test_override_must_be_exactly_one(self, monkeypatch):
        """A truthy-looking value is not enough; the opt-out has to be deliberate."""
        monkeypatch.setenv("QGP_I_UNDERSTAND_TESTS_WILL_WRITE_TO_THIS_DATABASE", "true")
        with pytest.raises(UnsafeTestDatabaseError):
            assert_test_database_is_local("postgresql+asyncpg://u:p@db.example.net/x")
