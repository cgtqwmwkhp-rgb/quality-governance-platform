"""The schema a deploy produces must hold every column the ORM will select.

Two properties, both asserted against a database built only by the alembic
chain — see ``_run026_migrated_schema`` for why the shared harness cannot host
them:

1. No mapped table is missing a column its model declares. A whole-entity ORM
   load emits every mapped column, so one absent column takes the whole table
   out, and that is what these assertions are calibrated to: the check is
   "``SELECT`` every mapped column of this table succeeds", executed, rather
   than a name comparison that has to be trusted.
2. Every ``created_by_id`` / ``updated_by_id`` in the database references
   ``users``. ``AuditTrailMixin`` declares both columns and attaches no
   ``ForeignKey``, so before this suite the database let an attribution column
   name a user that does not exist.

Both fail on the schema as it stood at Run026: 15 absent columns across eight
tables, and 54 unconstrained attribution columns across 30 tables.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from scripts.ops.run025._models import load_metadata
from scripts.ops.run026.audit_attribution_schema import (
    ATTRIBUTION_TARGET,
    DEFERRED_ABSENT_COLUMNS,
    DROPPED_PHYSICAL_TABLES,
)
from tests.integration._run026_migrated_schema import (
    ATTRIBUTION_COLUMNS,
    alembic_executable,
    create_migrated_database,
    drop_database,
    postgres_base_url,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def migrated():
    """A scratch database at alembic head, dropped when the module finishes.

    Module-scoped because the chain is 214 migrations: paying that per test
    would make the suite slow enough that someone would mark it skipped, and a
    skipped gate is not a gate. Every assertion below is read-only apart from
    the orphan probe, which rolls itself back.
    """
    base_url = postgres_base_url()
    if base_url is None:
        pytest.skip("needs PostgreSQL: this census reads information_schema and pg_constraint")
    if alembic_executable() is None:
        pytest.skip("needs the alembic console script on PATH to build the migrated schema")

    schema = create_migrated_database(base_url)
    try:
        yield schema
    finally:
        schema.dispose()
        drop_database(base_url, schema.name)


def _auditable_tables(migrated) -> list[str]:
    """Tables the database has that carry at least one attribution column."""
    present = migrated.tables()
    return sorted(
        table
        for table in present
        if migrated.columns(table) & set(ATTRIBUTION_COLUMNS)  # noqa: SIM118 - set intersection, not membership
    )


def test_every_declared_column_exists_in_the_migrated_schema(migrated):
    """No mapped table may be missing a column its model declares.

    Deliberately not filtered by ``_ALEMBIC_CHECK_EXCLUDED_TABLES``. That set
    defers *table-level* compare noise (ORM/migration naming drift, models
    without create coverage) and is a maintained register with named owners; it
    was never a licence for a declared column to be absent from a table the
    database does have. Filtering by it here is what hid four of these.
    """
    metadata = load_metadata()
    present_tables = migrated.tables()

    absent: list[str] = []
    for table_name, table in sorted(metadata.tables.items()):
        if table_name not in present_tables or table_name in DROPPED_PHYSICAL_TABLES:
            continue
        actual = migrated.columns(table_name)
        for column in sorted(table.c.keys()):
            if column in actual or (table_name, column) in DEFERRED_ABSENT_COLUMNS:
                continue
            absent.append(f"{table_name}.{column}")

    assert absent == [], (
        "the migration chain produces a schema that is missing columns the models declare. "
        "Every one of these makes a whole-entity ORM load of that table raise UndefinedColumn: "
        f"{absent}"
    )


def test_selecting_every_mapped_column_succeeds_for_auditable_tables(migrated):
    """Execute what the ORM emits, rather than comparing column names.

    A name comparison can be right about the names and wrong about whether the
    query runs. This issues the ``SELECT`` the ORM would build for a
    whole-entity load and lets PostgreSQL be the judge.
    """
    metadata = load_metadata()
    present_tables = migrated.tables()

    failures: list[str] = []
    for table_name in _auditable_tables(migrated):
        table = metadata.tables.get(table_name)
        if table is None or table_name not in present_tables:
            continue
        if any((table_name, column) in DEFERRED_ABSENT_COLUMNS for column in table.c.keys()):
            continue
        with migrated.engine.connect() as conn:
            try:
                conn.execute(sa.select(*table.c).limit(1))
            except sa.exc.ProgrammingError as exc:
                failures.append(f"{table_name}: {str(exc.orig).splitlines()[0]}")

    assert failures == [], "a plain whole-entity read of these tables fails against the migrated schema: " + repr(
        failures
    )


def test_every_attribution_column_references_users(migrated):
    """``created_by_id`` / ``updated_by_id`` must be constrained to ``users``.

    Enumerated from the database, not from ``Base.metadata``: a table with no
    model, or one whose name is in the exclusion register, still has to enforce
    attribution, and a model-driven sweep cannot see it.
    """
    unconstrained: list[str] = []
    for table in _auditable_tables(migrated):
        actual = migrated.columns(table)
        for column in ATTRIBUTION_COLUMNS:
            if column not in actual:
                continue
            if ATTRIBUTION_TARGET not in migrated.foreign_key_targets(table, column):
                unconstrained.append(f"{table}.{column}")

    assert unconstrained == [], (
        "these attribution columns have no foreign key to users, so they can name a user that "
        f"does not exist and nothing in the database objects: {unconstrained}"
    )


def test_the_constraint_actually_rejects_an_unknown_user(migrated):
    """Pin the behaviour, not just the catalogue entry.

    A constraint that exists but is ``NOT VALID``, or points somewhere else,
    would satisfy the census above and still let an orphan in. So one orphan is
    attempted for real and has to be refused. Rolled back either way.
    """
    table = "capa_items"
    if table not in migrated.tables():
        pytest.skip(f"{table} is not in the migrated schema")

    absent_user_id = (
        migrated.execute(f"SELECT coalesce(max(id), 0) + 1000 FROM {ATTRIBUTION_TARGET}")  # noqa: S608
    ).scalar()

    with migrated.engine.connect() as conn:
        transaction = conn.begin()
        try:
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(
                    sa.text(
                        f"INSERT INTO {table} (action_type, title, description, created_by_id) "  # noqa: S608
                        "VALUES ('corrective', 'orphan probe', 'probe', :user_id)"
                    ),
                    {"user_id": absent_user_id},
                )
        finally:
            transaction.rollback()
