"""``AuditTrailMixin`` must declare attribution as a reference, not a bare integer.

The mixin is the root cause of the unenforced-attribution drift. It declares
``created_by_id`` and ``updated_by_id`` and attaches no ``ForeignKey``, so every
table that takes its attribution columns from the mixin alone got two plain
integers — in the models, and therefore in anything built from the models, and
therefore in ``create_all``-built test databases too. 30 tables reached
production that way.

Fixing this only in migrations would leave the models still declaring a plain
integer while the database enforced a reference. ``alembic check`` would not
report it, because CI strips ``CreateForeignKeyOp``, so the drift would be real
and silent. These assertions are the model half of the fix, and they need no
database, so they run in the unit job on every commit.
"""

from __future__ import annotations

from scripts.ops.run025._models import load_metadata
from scripts.ops.run026.audit_attribution_schema import ATTRIBUTION_COLUMNS, ATTRIBUTION_TARGET
from src.domain.models.base import AuditTrailMixin
from src.infrastructure.database import Base

EXPECTED_TARGETS = frozenset({f"{ATTRIBUTION_TARGET}.id"})


def _mixin_tables() -> dict[str, object]:
    """``{tablename: mapped class}`` for every model that inherits the mixin."""
    load_metadata()
    return {
        mapper.class_.__tablename__: mapper.class_
        for mapper in Base.registry.mappers
        if issubclass(mapper.class_, AuditTrailMixin)
    }


def test_the_mixin_declares_both_attribution_columns():
    """Guard the premise: if the mixin stops declaring these, the rest is vacuous."""
    load_metadata()
    columns = {name for name, _ in AuditTrailMixin.__dict__.items()}
    for column in ATTRIBUTION_COLUMNS:
        assert column in columns or hasattr(AuditTrailMixin, column), (
            f"AuditTrailMixin no longer declares {column}. The suites that assert the database "
            "constrains it are calibrated to the mixin declaring it, so update them together."
        )


def test_every_mixin_table_declares_a_foreign_key_to_users():
    """Attribution columns must be declared as references to ``users.id``.

    Enumerated over the mapped classes rather than the mixin alone, because a
    consuming model may override either column, and an override that drops the
    reference is the same defect arriving by a different route.
    """
    unconstrained: list[str] = []
    for table_name, model in sorted(_mixin_tables().items()):
        table = model.__table__
        for column_name in ATTRIBUTION_COLUMNS:
            column = table.c.get(column_name)
            if column is None:
                unconstrained.append(f"{table_name}.{column_name} (not mapped)")
                continue
            targets = {str(fk.target_fullname) for fk in column.foreign_keys}
            if not targets & EXPECTED_TARGETS:
                unconstrained.append(f"{table_name}.{column_name} -> {sorted(targets) or 'nothing'}")

    assert unconstrained == [], (
        "these attribution columns are declared as plain integers, so nothing stops them naming "
        f"a user that does not exist: {unconstrained}"
    )


def test_attribution_columns_stay_nullable():
    """The reference must not become mandatory as a side effect of constraining it.

    Rows predating id-based attribution carry no ``created_by_id``, and the eight
    tables that gained the column in Run026 gained it empty on every existing
    row. ``NOT NULL`` here would make the migration unrunnable on any database
    with history, which is the trap the WCS-TEN2 ``tenant_id`` wave fell into.
    """
    mandatory: list[str] = []
    for table_name, model in sorted(_mixin_tables().items()):
        for column_name in ATTRIBUTION_COLUMNS:
            column = model.__table__.c.get(column_name)
            if column is not None and not column.nullable:
                mandatory.append(f"{table_name}.{column_name}")

    assert mandatory == [], (
        "attribution columns must stay nullable: rows predating id-based attribution have no "
        f"user to name, and a NOT NULL migration over them cannot run: {mandatory}"
    )
