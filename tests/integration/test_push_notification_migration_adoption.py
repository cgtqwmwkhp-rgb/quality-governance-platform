"""``20260903_push_notif`` against a database that already holds its tables (C-67).

What this pins
--------------
The production deploy of ``1e77f388`` aborted in "Run database migrations":

    Running upgrade 20260902_capa_vd_src -> 20260903_push_notif
    asyncpg.exceptions.DuplicateTableError: relation "push_subscriptions" already exists

Production carried both push tables with no ``alembic_version`` row naming this
revision -- orphans from the ``create_all`` era the models spent in a route
module. Staging did not carry them, migrated cleanly, and so nothing before
production could observe the difference. Neither the unit suite nor
``alembic_only_schema`` can: both start from a database where the tables are
absent, which is the one case the original migration handled.

So the harness here is the missing one -- a database migrated to the revision
*before* this one, with the tables already present, which is exactly the state
production was in.

Why a template database
-----------------------
Each case needs its own copy of the pre-revision schema, and building it costs a
full chain run (measured ~5s). PostgreSQL copies a database cheaply with
``CREATE DATABASE ... TEMPLATE``, so the chain runs once per module and each test
clones it. The template is never connected to after it is built, because
PostgreSQL refuses to copy a database that has sessions attached.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass
from typing import Iterator, Optional

import pytest
import sqlalchemy as sa

from tests.integration import _alembic_only_schema as harness

REVISION = "20260903_push_notif"
PREVIOUS_REVISION = "20260902_capa_vd_src"
TABLES = ("push_subscriptions", "notification_logs")


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the alembic console script against ``url``.

    The console script rather than ``python -c``, for the reason given in
    ``harness._alembic_executable``: this repository's own ``alembic/`` package
    shadows the installed library whenever the working directory leads ``sys.path``.
    """
    env = dict(os.environ)
    env["DATABASE_URL"] = url
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        [harness._alembic_executable(), *args],
        cwd=harness.REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _create_database(suite_url: str, name: str, template: Optional[str] = None) -> str:
    admin = sa.create_engine(harness._sync(suite_url), isolation_level="AUTOCOMMIT")
    clause = f'CREATE DATABASE "{name}"' + (f' TEMPLATE "{template}"' if template else "")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(clause))
    finally:
        admin.dispose()
    return sa.engine.make_url(suite_url).set(database=name).render_as_string(hide_password=False)


@dataclass(frozen=True)
class ScratchDatabase:
    """A database this test owns, at the revision before the one under test."""

    url: str
    engine: sa.Engine

    def table_names(self) -> set[str]:
        with self.engine.connect() as conn:
            return set(sa.inspect(conn).get_table_names())

    def stamped_revision(self) -> Optional[str]:
        with self.engine.connect() as conn:
            return conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()

    def create_from_models(self, *tables: str) -> None:
        """Reproduce what ``create_all`` left in production, from the same metadata."""
        import src.domain.models.push_notification  # noqa: F401 — registers both tables
        from src.domain.models.base import Base

        for table in tables:
            Base.metadata.tables[table].create(self.engine)

    def execute(self, statement: str) -> None:
        with self.engine.begin() as conn:
            conn.exec_driver_sql(statement)

    def scalar(self, statement: str) -> object:
        with self.engine.connect() as conn:
            return conn.exec_driver_sql(statement).scalar()


@pytest.fixture(scope="module")
def _pre_revision_template() -> Iterator[tuple[str, str]]:
    suite_url = os.environ["DATABASE_URL"]
    if not harness.is_postgres(suite_url):
        pytest.skip(
            "the migration chain is PostgreSQL-only, so a SQLite run cannot "
            "reproduce the state production was in. Set DATABASE_URL to "
            "PostgreSQL (CI does)."
        )

    name = f"qgp_push_adopt_template_{uuid.uuid4().hex[:8]}"
    url = _create_database(suite_url, name)

    result = _alembic(url, "upgrade", PREVIOUS_REVISION)
    if result.returncode != 0:
        harness.drop(suite_url, name)
        raise RuntimeError(
            f"alembic upgrade {PREVIOUS_REVISION} failed against a clean database, "
            "so this module cannot say anything about what the next revision does.\n"
            f"stdout:\n{result.stdout[-4000:]}\nstderr:\n{result.stderr[-4000:]}"
        )

    try:
        yield suite_url, name
    finally:
        harness.drop(suite_url, name)


@pytest.fixture
def scratch(_pre_revision_template: tuple[str, str]) -> Iterator[ScratchDatabase]:
    suite_url, template = _pre_revision_template
    name = f"qgp_push_adopt_{uuid.uuid4().hex[:12]}"
    url = _create_database(suite_url, name, template=template)
    engine = sa.create_engine(harness._sync(url))
    try:
        yield ScratchDatabase(url, engine)
    finally:
        engine.dispose()
        harness.drop(suite_url, name)


class TestTheHarnessIsTheStateProductionWasIn:
    """Without this, every assertion below could pass against the clean case."""

    def test_the_clone_is_at_the_previous_revision_without_the_push_tables(self, scratch: ScratchDatabase):
        assert scratch.stamped_revision() == PREVIOUS_REVISION
        assert set(TABLES).isdisjoint(scratch.table_names())


class TestUpgradeOverTablesThatAlreadyExist:
    def test_it_adopts_both_tables_and_keeps_their_rows(self, scratch: ScratchDatabase):
        """Production's case exactly: both tables present, revision unstamped."""
        scratch.create_from_models(*TABLES)
        scratch.execute(
            "INSERT INTO push_subscriptions (endpoint, p256dh_key, auth_key) "
            "VALUES ('https://push.example/adopted', 'p256dh', 'auth')"
        )

        result = _alembic(scratch.url, "upgrade", REVISION)

        assert result.returncode == 0, (
            "the revision still refuses a database that already has the tables, "
            f"which is the production failure.\nstdout:\n{result.stdout[-4000:]}\n"
            f"stderr:\n{result.stderr[-4000:]}"
        )
        assert scratch.stamped_revision() == REVISION
        assert set(TABLES) <= scratch.table_names()
        assert scratch.scalar("SELECT count(*) FROM push_subscriptions") == 1, (
            "the adopted table was recreated rather than adopted, so production "
            "would have lost its existing subscriptions"
        )

        combined = result.stdout + result.stderr
        for table in TABLES:
            assert f"adopted the existing {table!r}" in combined, (
                "the deploy log does not record that the table was adopted rather "
                "than created, which is the only trace that this environment held "
                f"orphan tables:\n{combined[-4000:]}"
            )

    def test_it_creates_the_absent_half_of_the_pair(self, scratch: ScratchDatabase):
        """Per table, not per revision.

        One table existing says nothing about the other. A revision-wide "return
        if present" would stamp itself here having created nothing, and
        ``push_subscriptions`` would be absent from a database recorded as
        migrated -- which is the defect C-67 set out to close, reintroduced by
        the fix for it.
        """
        scratch.create_from_models("notification_logs")

        result = _alembic(scratch.url, "upgrade", REVISION)

        assert result.returncode == 0, f"stdout:\n{result.stdout[-4000:]}\nstderr:\n{result.stderr[-4000:]}"
        assert scratch.stamped_revision() == REVISION
        assert set(TABLES) <= scratch.table_names(), (
            f"only {sorted(set(TABLES) & scratch.table_names())} exists after the "
            "upgrade, so the revision skipped a table it had to create"
        )


class TestUpgradeRefusesATableItCannotAdopt:
    def test_a_table_missing_columns_fails_the_deploy_and_is_not_stamped(self, scratch: ScratchDatabase):
        """The alternative is a green deploy over a schema the models cannot read.

        A precise failure naming the columns is the point: the deploy stops with
        the remedy in the log rather than stamping the revision and leaving the
        push endpoints to raise ``UndefinedColumn`` at runtime.
        """
        scratch.execute("CREATE TABLE push_subscriptions (id SERIAL PRIMARY KEY, endpoint TEXT NOT NULL UNIQUE)")

        result = _alembic(scratch.url, "upgrade", REVISION)

        assert result.returncode != 0, "a table missing seven columns was adopted silently"
        combined = result.stdout + result.stderr
        assert "DuplicateTable" not in combined, (
            "the failure came from PostgreSQL rejecting the CREATE rather than "
            "from the adoption check, so the log says 'already exists' instead of "
            f"which columns are missing:\n{combined[-4000:]}"
        )
        assert "push_subscriptions" in combined and "p256dh_key" in combined, (
            "the failure does not name the table and the missing column, so a "
            f"deploy log would not say what to reconcile:\n{combined[-4000:]}"
        )
        assert scratch.stamped_revision() == PREVIOUS_REVISION, (
            "the revision was stamped over a table it refused to adopt, so the "
            "next deploy would skip it and the schema would stay wrong"
        )
