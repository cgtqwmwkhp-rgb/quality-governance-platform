"""The dedupe index must be declared identically in the model and the migration.

Two independent things can go wrong with this index and neither shows up as a test
failure anywhere else.

The first is drift between the ORM declaration and the migration. The migration is
what builds the index in staging and production; the ORM declaration is what
``create_all`` builds in the SQLite test database, and what ``alembic check``
compares the migrated schema against. If they disagree, the constraint tests pass
against one shape while a different shape is deployed, and the drift ratchet starts
failing on ``notifications`` for reasons no one connects to this change.

The second is subtler and was found by measuring rather than reasoning:
``postgresql_where`` is dialect-scoped, so a declaration carrying only that one
compiles on SQLite to an index with *no* predicate. That index is a unique
constraint on ``(user_id, COALESCE(extra_data ->> 'dedupe_key', ''))`` across every
row in the table, and since almost no notification carries a ``dedupe_key`` it
allows each user exactly one notification in total. Verified against sqlite3
directly: the second ordinary notification for a user is rejected with
``UNIQUE constraint failed``. That would redden a large number of unrelated tests
with a message pointing at this index and no explanation of why. ``sqlite_where``
is what prevents it, so its presence is asserted here rather than left to whoever
next edits the model to rediscover.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex

from src.domain.models.notification import Notification

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20260914_compliance_notification_dedupe_index.py"

INDEX_NAME = "uq_notifications_compliance_dedupe"


def _load_migration() -> ModuleType:
    """Load the migration by path; ``alembic/versions`` is not an importable package.

    ``alembic.op`` is stubbed because the repo ships an empty ``alembic/__init__.py``
    that shadows the installed distribution once the repo root is on ``sys.path``.
    Nothing asserted here calls through ``op``.
    """
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("qgp_cs_notif_dedupe_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migration = _load_migration()


def _index() -> sa.Index:
    for index in Notification.__table__.indexes:
        if index.name == INDEX_NAME:
            return index
    raise AssertionError(f"{INDEX_NAME} is not declared on the Notification model")


def _normalise(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def test_index_is_declared_on_the_model() -> None:
    assert _index().unique is True, "a non-unique index constrains nothing and would dedupe nothing"


def test_migration_chains_from_wave0() -> None:
    assert migration.revision == "20260914_cs_notif_dedupe"
    assert (
        migration.down_revision == "20260913_cs_wave0"
    ), "the index has to be created after the tables whose notifications it dedupes"


def test_migration_ddl_matches_the_model_declaration() -> None:
    """The literal the migration executes must be what the ORM would emit.

    Compiled rather than string-compared against a second copy of the expression,
    so this fails if either side is edited alone.
    """
    compiled = _normalise(str(CreateIndex(_index()).compile(dialect=postgresql.dialect())))
    assert _normalise(migration.INDEX_DDL) == compiled, (
        "migration INDEX_DDL and the ORM declaration have diverged:\n"
        f"  migration: {_normalise(migration.INDEX_DDL)}\n"
        f"  model:     {compiled}"
    )


def test_migration_constants_match_the_index() -> None:
    assert migration.INDEX_NAME == INDEX_NAME
    assert migration.TABLE_NAME == Notification.__tablename__
    assert migration.ENTITY_TYPE == "compliance_requirement"


@pytest.mark.parametrize("dialect_name", ["postgresql", "sqlite"])
def test_both_dialects_carry_the_partial_predicate(dialect_name: str) -> None:
    """Neither dialect may compile to an unscoped index.

    Asserted per dialect rather than by reading ``dialect_options``, because what
    matters is the DDL that reaches the database.
    """
    dialect = postgresql.dialect() if dialect_name == "postgresql" else sqlite.dialect()
    ddl = _normalise(str(CreateIndex(_index()).compile(dialect=dialect)))
    assert "WHERE entity_type = 'compliance_requirement'" in ddl, (
        f"the {dialect_name} DDL has no predicate, so it constrains every row in the "
        f"table rather than compliance rows only: {ddl}"
    )


def test_sqlite_index_blocks_duplicates_without_touching_other_notifications() -> None:
    """Build the SQLite DDL for real and exercise it.

    This is the case that motivated the test: it passes only because
    ``sqlite_where`` is present, and its two halves fail in opposite directions if
    the predicate is dropped or the COALESCE is.
    """
    ddl = str(CreateIndex(_index()).compile(dialect=sqlite.dialect()))
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        "CREATE TABLE notifications (" " id INTEGER PRIMARY KEY, user_id INT, entity_type TEXT, extra_data TEXT);"
    )
    connection.execute(ddl)

    ordinary = "INSERT INTO notifications (user_id, entity_type, extra_data) VALUES (?, ?, NULL)"
    connection.execute(ordinary, (7, "incident"))
    connection.execute(ordinary, (7, "action"))

    compliance = "INSERT INTO notifications (user_id, entity_type, extra_data) VALUES (?, 'compliance_requirement', ?)"
    payload = '{"dedupe_key": "12:2026-09-01:due_7"}'
    connection.execute(compliance, (7, payload))

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(compliance, (7, payload))

    # A different band for the same requirement is a different notification.
    connection.execute(compliance, (7, '{"dedupe_key": "12:2026-09-01:overdue"}'))
    # As is the same band for a different recipient.
    connection.execute(compliance, (8, payload))

    total = connection.execute("SELECT count(*) FROM notifications").fetchone()[0]
    assert total == 5, "the index rejected a write it should have allowed"
