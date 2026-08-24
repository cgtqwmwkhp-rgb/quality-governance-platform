"""Every data-retention target must name a table that exists, and say so when it does not.

What this pins
--------------
``RETENTION_RULES`` carried ``notification_log`` while the model and the migration
both call the table ``notification_logs``. The 90-day push-notification policy was
documented, scheduled nightly at 02:00 UTC, and deleted nothing for as long as the
rule existed. Nothing failed visibly: the per-table handler logged
``"table %s skipped (may not exist)"`` -- a cause it had not checked -- and wrote a
``-1`` sentinel into a results dict nobody alerted on.

Two guards, because the name check alone would not have been enough:

* the target set is compared against the schema the models declare, which is cheap
  and dialect-free and would have caught the typo at review time;
* the handler is made to fire against a real database and its warning is required
  to carry the table *and* the error, so the next misnamed target is diagnosable
  from one line of the nightly log rather than invisible.

Why the isolation property is not asserted here
-----------------------------------------------
The blast radius of a failing target -- on PostgreSQL the aborted transaction
turns the closing COMMIT into a rollback, so *no* table is purged -- is not
observable on SQLite, which does not abort transactions. A SQLite assertion about
it would pass whether or not the defect were fixed. That property is pinned in
``tests/integration/test_data_retention_sweep.py`` against PostgreSQL.
"""

from __future__ import annotations

import functools
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa

# celery_app imports settings at module load; keep local/dev defaults safe.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/quality_governance",
)

from src.infrastructure.tasks.cleanup_tasks import RETENTION_RULES  # noqa: E402

#: Targets that name no declared table, with the reason each is still listed.
#:
#: Declared rather than derived: deriving it from "targets absent from the metadata"
#: would make the assertion circular and the set could then change in silence. An
#: entry earns its place by being a decision someone has taken; ``notification_log``
#: never was, which is why it is not here.
#:
#: Now empty, and the emptiness is the point. ``investigations`` was listed here
#: because no such table exists; rather than guess which of the nine investigation
#: tables a horizon covers, the rule was removed from ``RETENTION_RULES`` entirely. A
#: rule that cannot name a table is not an excused defect, it is not a rule.
KNOWN_UNBACKED_TARGETS: frozenset[str] = frozenset()

#: Rules whose table exists but whose date column does not, same register rules.
#:
#: Also now empty. ``audit_log_entries.created_at`` was excused here because the table
#: times entries with ``timestamp``, and repointing the rule looked dangerous: the
#: documented horizon is 2555 days and the rule said 365, so a correct column name
#: would have begun purging a tamper-evident hash chain seven times too early.
#:
#: That danger has been removed at its source rather than by leaving a column name
#: wrong. The rule now takes its horizon from ``DEFAULT_RETENTION_POLICIES["audit_logs"]``,
#: which is 2555 days and ``soft_delete_first``, so the sweep refuses to hard-delete it
#: at all. The column name can therefore be truthful without being dangerous.
KNOWN_WRONG_DATE_COLUMNS: frozenset[tuple[str, str]] = frozenset()


#: Reads the whole declared schema without importing it into this process.
#:
#: Two constraints force the subprocess. Importing ``src.domain.models`` alone is
#: not enough -- its ``__init__`` does not reach every model file, and probing
#: through it reports ``audit_log_entries`` and ``near_misses`` as absent when both
#: plainly exist. But importing every model module here registers tables on the
#: process-wide ``Base.metadata``, and other suites read that same object: doing it
#: in-process makes ``test_delete_cascade_audit_visibility`` fail with two workflow
#: cascades its register does not carry, purely because this module ran first. A
#: child interpreter answers the question and takes its metadata with it.
_PROBE = """
import importlib, json, pkgutil
import src.domain.models as models_pkg
for _, name, _ in pkgutil.iter_modules(models_pkg.__path__):
    importlib.import_module("src.domain.models." + name)
from src.domain.models.base import Base
print(json.dumps({name: [c.name for c in table.columns] for name, table in Base.metadata.tables.items()}))
"""


@functools.lru_cache(maxsize=1)
def _declared_schema() -> dict[str, tuple[str, ...]]:
    """``{table: (column, ...)}`` for every table the running application declares."""
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root)
    env.setdefault("TESTING", "1")

    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-c", _PROBE],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "could not load the declared schema, so this module cannot say whether "
            f"a retention target is real.\nstdout:\n{completed.stdout[-2000:]}\n"
            f"stderr:\n{completed.stderr[-2000:]}"
        )

    schema = json.loads(completed.stdout.strip().splitlines()[-1])
    assert len(schema) > 200, f"only {len(schema)} tables loaded; the checks below would be vacuous"
    return {table: tuple(columns) for table, columns in schema.items()}


class TestEveryTargetNamesARealTable:
    def test_the_push_notification_rule_matches_the_model(self):
        """Pinned to ``NotificationLog.__tablename__`` rather than to a literal.

        The rule and the model disagreeing is the whole defect, so the assertion
        reads the name off the model instead of restating it.
        """
        from src.domain.models.push_notification import NotificationLog

        targets = {rule.table for rule in RETENTION_RULES}

        assert NotificationLog.__tablename__ in targets, (
            f"no retention rule targets {NotificationLog.__tablename__!r}, so the "
            "90-day push-notification policy in docs/privacy/data-retention-policy.md "
            "deletes nothing"
        )
        assert "notification_log" not in targets, (
            "the singular 'notification_log' is back in RETENTION_RULES; no such "
            "table exists, so the rule silently purges nothing"
        )

    def test_no_target_is_unbacked_beyond_the_recorded_exceptions(self):
        """A target naming no table is a rule that cannot delete a row.

        The recorded set is compared for equality, not containment: an entry that
        gets a real table must be removed from ``KNOWN_UNBACKED_TARGETS``, so the
        register cannot quietly grow stale and keep a live defect excused.
        """
        declared = _declared_schema()
        unbacked = {rule.table for rule in RETENTION_RULES if rule.table not in declared}

        assert unbacked == KNOWN_UNBACKED_TARGETS, (
            f"retention targets naming no declared table: {sorted(unbacked)}; "
            f"recorded and accepted: {sorted(KNOWN_UNBACKED_TARGETS)}. Every rule "
            "in that difference deletes nothing, silently."
        )

    def test_the_retention_columns_exist_on_the_tables_they_filter(self):
        """A right table with a wrong date column fails the same silent way.

        ``notification_logs`` was only the misnaming that got noticed. A rule
        filtering on a column its table does not have raises just as quietly and
        deletes just as little, so both shapes are checked here.
        """
        declared = _declared_schema()

        wrong = {
            (rule.table, rule.date_column)
            for rule in RETENTION_RULES
            if rule.table in declared and rule.date_column not in declared[rule.table]
        }

        assert wrong == KNOWN_WRONG_DATE_COLUMNS, (
            f"retention rules filtering on a column their table does not have: "
            f"{sorted(wrong)}; recorded and accepted: {sorted(KNOWN_WRONG_DATE_COLUMNS)}. "
            "Each one purges nothing, silently."
        )


class TestAFailingTargetIsVisibleInTheLog:
    """The handler must name the table and the error, not assert an unchecked cause."""

    @pytest.fixture
    def empty_sqlite_engine(self, tmp_path, monkeypatch):
        """A database with none of the target tables, so every rule fails.

        SQLite is adequate *for the logging assertion*: the point is what the
        handler writes when a DELETE raises, and ``OperationalError: no such
        table`` reaches the handler the same way ``UndefinedTable`` does.
        """
        engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'retention.db'}")
        import src.infrastructure.database as database_module

        monkeypatch.setattr(database_module, "sync_engine", engine)
        yield engine
        engine.dispose()

    def test_the_warning_names_the_table_and_the_error(self, empty_sqlite_engine, caplog):
        from src.infrastructure.tasks.cleanup_tasks import run_data_retention

        with caplog.at_level("WARNING"):
            result = run_data_retention.apply().get()

        assert result["status"] == "completed", "one unusable table must not abort the whole sweep"

        warnings = [record.getMessage() for record in caplog.records if record.levelname == "WARNING"]
        # Only rules the sweep actually attempts can fail. A policy-governed table is
        # skipped before any SQL is built, so it never raises and must not be expected to
        # warn -- it is accounted for in ``held``, asserted below.
        for table in (rule.table for rule in RETENTION_RULES if rule.may_hard_delete):
            named = [message for message in warnings if table in message]
            assert named, f"nothing was logged at WARNING for the failed table {table!r}"
            assert any("OperationalError" in message or "no such table" in message for message in named), (
                f"the warning for {table!r} does not carry the error that stopped it: "
                f"{named!r}. Without it a misnamed target reads as routine, which is "
                "how 'skipped (may not exist)' hid this defect."
            )

    def test_a_failed_table_is_not_reported_as_a_purge(self, empty_sqlite_engine):
        from src.infrastructure.tasks.cleanup_tasks import run_data_retention

        result = run_data_retention.apply().get()
        purged, held = result["purged"], result["held"]

        # Every rule is still accounted for, but across two outcomes now: attempted and
        # failed, or deliberately not attempted. The original single-dict assertion is
        # preserved as this union -- what matters is that no rule vanishes from the report.
        assert set(purged) | set(held) == {rule.table for rule in RETENTION_RULES}
        assert set(held) == {rule.table for rule in RETENTION_RULES if not rule.may_hard_delete}
        assert all(count == -1 for count in purged.values()), (
            f"a table that could not be read was reported as purged: {purged}. A "
            "positive count for a DELETE that never committed is worse than a gap."
        )


class TestASoundTargetIsActuallyPurged:
    """The narrow SQLite case: right name, table present, old rows must go.

    Discriminating for the name only. It cannot speak to the commit behaviour a
    failing sibling causes -- see this module's docstring.
    """

    def test_old_notification_logs_go_and_recent_ones_stay(self, tmp_path, monkeypatch):
        from src.domain.models.push_notification import NotificationLog
        from src.infrastructure.tasks.cleanup_tasks import run_data_retention

        engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'retention.db'}")
        NotificationLog.__table__.create(engine)

        now = datetime.utcnow()
        with engine.begin() as conn:
            for label, created_at in (
                ("stale", now - timedelta(days=120)),
                ("just-inside", now - timedelta(days=89)),
            ):
                conn.execute(
                    sa.text(
                        "INSERT INTO notification_logs (notification_type, title, channel, created_at) "
                        "VALUES ('push', :title, 'push', :created_at)"
                    ),
                    {"title": label, "created_at": created_at},
                )

        import src.infrastructure.database as database_module

        monkeypatch.setattr(database_module, "sync_engine", engine)

        purged = run_data_retention.apply().get()["purged"]

        assert purged["notification_logs"] == 1, (
            f"the 90-day rule purged {purged['notification_logs']} rows, expected 1 "
            "(-1 means the DELETE raised, which is what a misnamed target does)"
        )
        with engine.connect() as conn:
            surviving = conn.execute(sa.text("SELECT title FROM notification_logs")).scalars().all()
        assert surviving == ["just-inside"], f"wrong rows survived the 90-day cutoff: {surviving}"

        engine.dispose()
