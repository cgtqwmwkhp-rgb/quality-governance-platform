"""C-67 follow-up: the create migration must survive a table that already exists.

``20260903_push_notif`` shipped an unconditional ``CREATE TABLE`` on the strength
of a claim about production -- that it lacked both tables, as staging did.
Production had them, with no ``alembic_version`` row for the revision, left by
the ``create_all`` era these models spent in a route module. The production
deploy aborted with ``DuplicateTableError: relation "push_subscriptions" already
exists`` and no migration after it ran.

Two halves of the fix need no database and are pinned here: the migration still
mirrors the models column for column (#1442's requirement, so the drift ratchet
stays quiet), and adopting a pre-existing table checks the shape being adopted
rather than trusting it. The end-to-end behaviour against a database that already
holds the tables is in
``tests/integration/test_push_notification_migration_adoption.py``; column
*types* are the drift gate's job, which runs ``alembic check`` on every PR.

The migration is loaded by file path because ``alembic/versions`` is not an
importable package, and ``alembic.op`` is stubbed for the load: the repo ships an
empty ``alembic/__init__.py`` that shadows the installed distribution once the
repo root is on ``sys.path``. Nothing here goes through ``op`` -- the helpers
under test take an inspector.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import sqlalchemy as sa

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20260903_push_notification_tables.py"


def _load_migration() -> ModuleType:
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("qgp_push_notification_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migration = _load_migration()

COLUMN_FACTORIES = {
    "push_subscriptions": migration._push_subscriptions_columns,
    "notification_logs": migration._notification_logs_columns,
}


@pytest.mark.parametrize("table", sorted(COLUMN_FACTORIES))
def test_the_migration_names_exactly_the_columns_the_model_declares(table: str):
    """The adoption check is only as good as this list.

    A column on the model but not here would be created on a fresh database by
    ``create_all`` and by nothing else, and adoption would pass a production
    table that lacks it. A column here but not on the model is drift the ratchet
    would report on the next PR.
    """
    import src.domain.models.push_notification  # noqa: F401 — registers both tables

    from src.domain.models.base import Base

    model_columns = sorted(column.name for column in Base.metadata.tables[table].columns)
    migration_columns = sorted(column.name for column in COLUMN_FACTORIES[table]())

    assert migration_columns == model_columns, (
        f"{table}: migration and model disagree. Only on the migration: "
        f"{sorted(set(migration_columns) - set(model_columns))}; only on the model: "
        f"{sorted(set(model_columns) - set(migration_columns))}"
    )


@pytest.mark.parametrize("table", sorted(COLUMN_FACTORIES))
def test_the_columns_are_rebuilt_on_every_call(table: str):
    """A ``Column`` may only ever be attached to one ``Table``.

    Module-level column objects would work for the single ``upgrade()`` a
    deployment runs and fail the moment anything called it twice in one process,
    which is exactly what a test harness does.
    """
    first = COLUMN_FACTORIES[table]()
    second = COLUMN_FACTORIES[table]()

    assert [column.name for column in first] == [column.name for column in second]
    assert all(a is not b for a, b in zip(first, second))


def _sqlite_inspector(conn, ddl: str) -> sa.Inspector:
    conn.exec_driver_sql(ddl)
    return sa.inspect(conn)


def test_adoption_refuses_a_table_that_is_missing_columns():
    """The failure the unconditional CREATE could not express.

    Stamping the revision over a half-shaped table would record the schema as
    migrated while every read of the entity still failed -- the same silent
    wrongness that produced the incident, and harder to find than a
    DuplicateTable.
    """
    expected = [column.name for column in migration._push_subscriptions_columns()]

    with sa.create_engine("sqlite://").begin() as conn:
        inspector = _sqlite_inspector(
            conn, "CREATE TABLE push_subscriptions (id INTEGER PRIMARY KEY, endpoint TEXT NOT NULL)"
        )

        assert migration._missing_columns(inspector, "push_subscriptions", expected) == [
            "user_id",
            "p256dh_key",
            "auth_key",
            "user_agent",
            "is_active",
            "created_at",
            "last_used_at",
        ]

        with pytest.raises(RuntimeError) as raised:
            migration._adopt(inspector, "push_subscriptions", expected)

    message = str(raised.value)
    assert "push_subscriptions" in message, f"a deploy log would not say which table: {message}"
    assert "p256dh_key" in message, f"a deploy log would not say what is missing: {message}"


def test_adoption_accepts_a_table_that_carries_extra_columns():
    """Extras are tolerated deliberately.

    A ``create_all``-era table may hold columns no current model names. That is
    drift this revision cannot fix and does not stop the models reading the
    table, so refusing it would block a deployment over something the migration
    has no answer for.
    """
    columns = ", ".join(f"{column.name} TEXT" for column in migration._notification_logs_columns())
    expected = [column.name for column in migration._notification_logs_columns()]

    with sa.create_engine("sqlite://").begin() as conn:
        inspector = _sqlite_inspector(conn, f"CREATE TABLE notification_logs ({columns}, retired_flag TEXT)")

        assert migration._missing_columns(inspector, "notification_logs", expected) == []
        migration._adopt(inspector, "notification_logs", expected)
