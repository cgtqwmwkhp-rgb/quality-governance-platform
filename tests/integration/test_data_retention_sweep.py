"""``run_data_retention`` against PostgreSQL, where a failing rule aborts the transaction.

What this pins
--------------
Two defects, one of which is invisible without a real PostgreSQL server.

The first is the misnamed target: ``RETENTION_RULES`` said ``notification_log``
where the model and ``20260903_push_notif`` both say ``notification_logs``, so the
documented 90-day push-notification policy deleted nothing.

The second is why fixing the name alone would still have deleted nothing. Every
rule ran inside one ``engine.begin()``. On PostgreSQL the first failing statement
aborts the whole transaction: each later ``DELETE`` then raises
``InFailedSqlTransaction``, is caught by the same per-table handler, and -- this is
the part no log showed -- the closing ``COMMIT`` is degraded by the server to a
rollback. Measured on PostgreSQL 14.20 before the fix: the task reported
``{'audit_log_entries': 3, ... 'near_misses': 3}`` and every row was still there
afterwards. Positive purge counts for deletions that never happened.

The sweep therefore has two rules that cannot succeed against the deployed schema
-- ``audit_log_entries`` filters on a ``created_at`` the table does not have, and
``investigations`` names no table at all -- one of which precedes every other rule.
That is why nothing had ever been purged, by any rule, on any night.

Why PostgreSQL and not the SQLite harness
-----------------------------------------
SQLite does not abort a transaction on a failed statement, so the surviving rules
commit there whether or not the fix is present and an assertion about it would be
green either way. This is the same reasoning as ``_fabricated_zero_scratch``.

Why a database of its own
-------------------------
The shared harness is recreated and reseeded around every test by autouse
fixtures, and this task deletes by wall-clock age across eight tables. A sweep
pointed at the shared database would be reaching into rows other tests own. A
template built once per module and cloned per test costs one ``create_all``.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import Iterator

import pytest
import sqlalchemy as sa

from tests.integration import _alembic_only_schema as harness

PUSH_RETENTION_DAYS = 90


#: A rule that cannot possibly succeed, used to keep the isolation property under test.
#:
#: This module originally leaned on two *real* broken rules for that -- a wrong column on
#: ``audit_log_entries`` and an ``investigations`` table that does not exist. Both have
#: since been fixed at the source, so depending on them would mean depending on defects
#: staying unfixed. A synthetic rule pins the same property and cannot rot: the isolation
#: guarantee is about what a failing rule does to its siblings, not about which rule fails.
def _impossible_rule():
    from src.infrastructure.tasks.cleanup_tasks import RetentionRule

    return RetentionRule("table_that_does_not_exist", "created_at", operational_days=1)


def _push_rule():
    from src.infrastructure.tasks.cleanup_tasks import RetentionRule

    return RetentionRule("notification_logs", "created_at", operational_days=PUSH_RETENTION_DAYS)


def _create_database(suite_url: str, name: str, template: str | None = None) -> str:
    admin = sa.create_engine(harness._sync(suite_url), isolation_level="AUTOCOMMIT")
    clause = f'CREATE DATABASE "{name}"' + (f' TEMPLATE "{template}"' if template else "")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(clause))
    finally:
        admin.dispose()
    return sa.engine.make_url(suite_url).set(database=name).render_as_string(hide_password=False)


@pytest.fixture(scope="module")
def _schema_template() -> Iterator[tuple[str, str]]:
    suite_url = os.environ.get("DATABASE_URL", "")
    if not harness.is_postgres(suite_url):
        pytest.skip(
            "a failing statement only aborts the surrounding transaction on "
            "PostgreSQL, and that abort is half of what this module measures. "
            "Set DATABASE_URL to PostgreSQL (CI does)."
        )

    import importlib
    import pkgutil

    import src.domain.models as models_pkg

    for _, name, _ in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module(f"src.domain.models.{name}")
    from src.domain.models.base import Base

    template = f"qgp_retention_template_{uuid.uuid4().hex[:8]}"
    url = _create_database(suite_url, template)
    engine = sa.create_engine(harness._sync(url))
    try:
        Base.metadata.create_all(engine)
    finally:
        # PostgreSQL refuses to clone a database that has sessions attached.
        engine.dispose()

    try:
        yield suite_url, template
    finally:
        harness.drop(suite_url, template)


@pytest.fixture
def retention_db(_schema_template: tuple[str, str], monkeypatch) -> Iterator[sa.Engine]:
    """A database this test owns, wired in as the sync engine the task reads."""
    suite_url, template = _schema_template
    name = f"qgp_retention_{uuid.uuid4().hex[:12]}"
    url = _create_database(suite_url, name, template=template)
    engine = sa.create_engine(harness._sync(url))

    import src.infrastructure.database as database_module

    monkeypatch.setattr(database_module, "sync_engine", engine)
    try:
        yield engine
    finally:
        engine.dispose()
        harness.drop(suite_url, name)


def _seed_notification_logs(engine: sa.Engine, ages_in_days: dict[str, int]) -> None:
    with engine.begin() as conn:
        for title, age in ages_in_days.items():
            conn.execute(
                sa.text(
                    "INSERT INTO notification_logs (notification_type, title, channel, created_at) "
                    "VALUES ('push', :title, 'push', :created_at)"
                ),
                {"title": title, "created_at": datetime.utcnow() - timedelta(days=age)},
            )


def _titles(engine: sa.Engine) -> list[str]:
    """Read on a *new* connection, so nothing uncommitted can be mistaken for a purge."""
    with engine.connect() as conn:
        return sorted(conn.execute(sa.text("SELECT title FROM notification_logs")).scalars().all())


def _run_sweep() -> dict:
    from src.infrastructure.tasks.cleanup_tasks import run_data_retention

    return run_data_retention.apply().get()


class TestTheHarnessIsTheStateProductionIsIn:
    """Without this, every assertion below could be passing for the wrong reason."""

    def test_the_push_table_exists_and_the_synthetic_failure_really_fails(self, retention_db: sa.Engine):
        with retention_db.connect() as conn:
            tables = set(sa.inspect(conn).get_table_names())
            columns = {column["name"] for column in sa.inspect(conn).get_columns("audit_log_entries")}

        assert "notification_logs" in tables, "the table the 90-day rule targets is absent from the harness"
        assert _impossible_rule().table not in tables, (
            "the harness has a table by the name this module uses for a guaranteed "
            "failure, so the isolation assertions below would pass vacuously"
        )
        # Records why the audit rule is now safe to point at a real column: it is not the
        # column that protects the hash chain, it is the policy refusing a hard delete.
        assert "created_at" not in columns and "timestamp" in columns, (
            "audit_log_entries no longer times entries with 'timestamp', so the "
            "retention rule's column name needs revisiting"
        )


class TestThePushNotificationPolicyActuallyDeletes:
    def test_rows_past_the_horizon_are_gone_and_recent_ones_remain(self, retention_db: sa.Engine):
        """The whole point: committed deletions, read back on a fresh connection.

        This is the assertion that fails against the misnamed target *and* against
        a correctly named target still sharing one transaction with the two broken
        rules -- in the second case because the ``COMMIT`` becomes a rollback.
        """
        _seed_notification_logs(
            retention_db,
            {
                "well-past": PUSH_RETENTION_DAYS + 200,
                "just-past": PUSH_RETENTION_DAYS + 1,
                "just-inside": PUSH_RETENTION_DAYS - 1,
                "today": 0,
            },
        )

        purged = _run_sweep()["purged"]

        assert purged["notification_logs"] == 2, (
            f"the 90-day rule reported {purged['notification_logs']} rows "
            "(-1 means the DELETE raised, which is what the misnamed target did)"
        )
        assert _titles(retention_db) == ["just-inside", "today"], (
            f"rows past the 90-day horizon survived the sweep: {_titles(retention_db)}. "
            "A reported count with the rows still present is the silent-rollback "
            "defect: the sweep's COMMIT was degraded to a rollback by the abort "
            "that a later broken rule caused."
        )

    def test_a_rule_that_cannot_run_is_reported_as_a_failure(self, retention_db: sa.Engine, monkeypatch):
        """The fix must not paper over a broken rule by making the sweep look clean."""
        import src.infrastructure.tasks.cleanup_tasks as tasks

        monkeypatch.setattr(tasks, "RETENTION_RULES", (_impossible_rule(), _push_rule()))

        purged = _run_sweep()["purged"]
        table = _impossible_rule().table

        assert purged[table] == -1, f"{table} is reported as a successful purge ({purged[table]}) when it cannot run"

    def test_a_policy_governed_table_is_never_hard_deleted(self, retention_db: sa.Engine):
        """The guard that matters, measured against PostgreSQL rather than reasoned about.

        ``incidents`` is governed by a 2555-day policy marked ``soft_delete_first``, and
        this sweep has no soft-delete phase. Before the guard existed the rule carried a
        hand-written 365 days and a bare ``DELETE``, cascading to actions and running
        sheets, at 02:00, unattended. Seed a row far past every horizon and require it to
        survive.
        """
        # Inserted through the ORM rather than raw SQL: several NOT NULL columns on this
        # table carry Python-side defaults, which a text INSERT does not apply, so raw SQL
        # here means enumerating constraints until the statement happens to work.
        from sqlalchemy.orm import Session

        from src.domain.models.incident import Incident
        from src.domain.models.tenant import Tenant

        ancient = datetime.utcnow() - timedelta(days=4000)
        with Session(retention_db) as session:
            # The harness template carries schema but no rows, and incidents.tenant_id is
            # a foreign key.
            session.add(Tenant(name="Retention Guard", slug="retention-guard", admin_email="guard@example.com"))
            session.flush()
            session.add(
                Incident(
                    reference_number="RET-GUARD-001",
                    title="ancient",
                    description="far past every retention horizon",
                    tenant_id=1,
                    incident_date=ancient,
                    reported_date=ancient,
                    created_at=ancient,
                )
            )
            session.commit()

        result = _run_sweep()

        assert "incidents" in result["held"], (
            "incidents was not held back by its retention policy, so this sweep is "
            f"free to hard-delete a statutory record: held={result['held']}"
        )
        assert "incidents" not in result["purged"], "a policy-governed table reached the DELETE path"

        with retention_db.connect() as conn:
            survivors = (
                conn.execute(sa.text("SELECT reference_number FROM incidents WHERE reference_number = 'RET-GUARD-001'"))
                .scalars()
                .all()
            )
        assert survivors == ["RET-GUARD-001"], "a 4000-day-old incident was destroyed despite a 2555-day policy"

    def test_a_rule_failing_before_the_push_rule_does_not_block_it(self, retention_db: sa.Engine, monkeypatch):
        """Ordering must not decide whether a sound rule runs.

        ``audit_log_entries`` already precedes the push rule, but it is a wrong
        *column* on a real table. This substitutes a wholly absent table so the
        harder failure -- the one that produced ``UndefinedTable`` -- is also
        pinned ahead of a rule that must still succeed.
        """
        import src.infrastructure.tasks.cleanup_tasks as tasks

        monkeypatch.setattr(tasks, "RETENTION_RULES", (_impossible_rule(), _push_rule()))
        _seed_notification_logs(retention_db, {"well-past": PUSH_RETENTION_DAYS + 200, "today": 0})

        purged = _run_sweep()["purged"]

        assert purged["table_that_does_not_exist"] == -1
        assert purged["notification_logs"] == 1
        assert _titles(retention_db) == [
            "today"
        ], f"a preceding failure took the push purge down with it: {_titles(retention_db)}"

    def test_the_sweep_reports_completed_rather_than_retrying(self, retention_db: sa.Engine):
        """One unusable table must not turn into a failed task and three retries."""
        assert _run_sweep()["status"] == "completed"


class TestAFailedRuleIsVisible:
    def test_the_warning_names_the_table_and_the_postgres_error(self, retention_db: sa.Engine, caplog, monkeypatch):
        """``UndefinedTable``/``UndefinedColumn`` must reach the log, not just ``-1``.

        The previous wording -- ``"table %s skipped (may not exist)"`` -- asserted a
        cause it had not checked and dropped the exception entirely, which is why a
        misnamed target read as routine housekeeping for as long as it did.
        """
        import src.infrastructure.tasks.cleanup_tasks as tasks

        # A wrong table and a wrong column raise different PostgreSQL errors, and the
        # handler must carry either. The wrong column is put on ``token_blacklist`` rather
        # than on the push table, so the final assertion below -- that a rule which
        # succeeded is not warned about -- still means something.
        monkeypatch.setattr(
            tasks,
            "RETENTION_RULES",
            (
                _impossible_rule(),
                tasks.RetentionRule("token_blacklist", "no_such_column", operational_days=1),
                _push_rule(),
            ),
        )

        with caplog.at_level("WARNING"):
            _run_sweep()

        warnings = [record.getMessage() for record in caplog.records if record.levelname == "WARNING"]

        for table, expected_error in (
            (_impossible_rule().table, "UndefinedTable"),
            ("token_blacklist", "UndefinedColumn"),
        ):
            named = [message for message in warnings if table in message]
            assert named, f"nothing was logged at WARNING for the failed rule {table!r}"
            assert any(expected_error in message for message in named), (
                f"the warning for {table!r} does not carry the PostgreSQL error "
                f"({expected_error}) that stopped it: {named!r}"
            )

        assert not [message for message in warnings if "notification_logs" in message], (
            "the rule that succeeded was also warned about, which would make the "
            "warning useless for spotting the rules that did not"
        )
