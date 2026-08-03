"""Converge the remaining seven IMS / ISO27001 tables with their models (C-24, #1526).

Revision ID: 20260909_iso_absorb
Revises: 20260908_soa_align
Create Date: 2026-09-09

What was wrong
--------------
Nine names were left on ``_ALEMBIC_CHECK_EXCLUDED_TABLES`` after
``20260908_soa_align``, carrying 144 autogenerate operations between them that
no gate reported, because ``include_object`` removes the table from the
comparison before a single column is looked at. Measured on PostgreSQL 16.14
against a database built by ``alembic upgrade head`` at ``20260908_soa_align``:

    DropColumnOp        50   columns the database has and the model did not
    AlterColumnOp       49   25 nullability, 24 type
    CreateForeignKeyOp  16   9 option-only, 7 genuinely absent
    DropIndexOp         14   indexes the database has and the model did not
    DropConstraintOp     9   8 the paired foreign key, 1 unique
    CreateTableCommentOp 1
    AddColumnOp          0   -- nothing here is query-breaking

Unlike ``soa_control_entries``, none of these tables is unreadable: the model
declares no column the database lacks, so ``select(Model)`` works and the
endpoints in ``src/api/routes/iso27001.py`` above them are live. What the
drift hides is the reverse -- 50 columns of real ISO 27001 evidence that the
ORM cannot see, and which autogenerate would offer to drop.

Which side moves, and why
-------------------------
The rule is the one ``20260908_soa_align`` used: the side that moves is the
side whose move cannot lose or reject data. Applied per class of disagreement:

* **50 database-only columns** -> the *model* absorbs them, in the shape the
  database has, including the ``NOT NULL`` + server default on the six that
  carry one. Nothing is dropped and nothing is renamed. Several sit beside a
  later column that might have been meant to replace them --
  ``plan_name`` beside ``name``, ``resource_name`` beside ``system_name``,
  ``findings`` beside ``findings_details``, ``notification_required`` beside
  ``regulatory_notification_required``. ``20260407_iso27001_drift_02`` added
  the later one *beside* the original rather than migrating the data, so both
  are kept: deciding that one supersedes the other is an IMS decision about
  live certification evidence, and this migration does not make it (#1398).

* **25 nullability disagreements** (model ``NOT NULL``, database nullable)
  -> the *model* moves. ``20260407_iso27001_drift_02`` added these columns
  nullable on purpose, recording that existing rows could not satisfy
  ``NOT NULL`` and that the application layer supplies the value on new rows.
  Enforcing the model's claim now would need a value invented for every
  historic row of ``granted_date``, ``effective_date``, ``scope``,
  ``category`` and the rest -- on certification evidence. The requirement is
  not lost: it is enforced where it always actually was, in the request
  schemas (``AccessControlCreate.granted_date``, ``BCPCreate.scope`` ...),
  and the read paths already null-guard these fields. Enforcing any of them in
  the database is a per-column expand exercise with the IMS owner, tracked on
  #1526.

* **8 ``jsonb`` columns typed ``JSON`` in the model** -> the *model* moves, to
  the ``JSON().with_variant(JSONB, "postgresql")`` idiom already used by
  ``governed_knowledge.py``. Converting the database to ``json`` would rewrite
  every table and give up containment operators and GIN indexing.

* **``information_assets.business_value``**, ``text`` in the database and
  ``String(50)`` in the model -> the *model* widens. Narrowing the column
  would truncate.

* **16 ``varchar`` columns narrower in the database than in the model** ->
  the *database* widens, below. This is the one case where the database moves,
  and it is the ``implementation_status`` argument from ``20260908_soa_align``
  applied fifteen more times: widening a ``varchar`` in PostgreSQL is a
  catalogue-only change with no rewrite and no rejected value, and it closes a
  live failure -- a 150-character ``threat_source`` is accepted by the request
  schema today and rejected by ``varchar(100)`` with a 500.

* **16 foreign keys** -> 9 differ only in ``ON DELETE``, which the database has
  as ``SET NULL`` and the model did not declare; the model now declares it.
  The remaining 7 are absent from the database and are created here, all
  ``SET NULL``, matching every sibling foreign key in this cluster. ``SET NULL``
  rather than the model's silent default of ``NO ACTION`` deliberately: these
  are ``owner_id`` / ``reported_by_id`` style columns, all nullable, each with
  a ``_name`` column beside it that keeps the human-readable value, and
  ``NO ACTION`` would make deleting a user fail instead.

* **14 indexes and 1 unique constraint** the database has -> the model declares
  them. No index is created or dropped here.

* **1 table comment** the model declares and the database lacks -> set below.

Reversibility
-------------
``downgrade`` narrows the sixteen ``varchar`` columns back and drops the seven
foreign keys and the comment. The narrowing **refuses** rather than truncate:
if any row holds a value longer than the original limit it raises, for the
reason ``20260908_soa_align`` gave -- silently shortening a compliance state is
worse than a failed downgrade. Each step is conditional on the current state
rather than on this migration having produced it, so on a database that already
carried one of the seven foreign keys the downgrade removes it; that is the same
trade ``20260908_soa_align``'s column drops make, and unlike a column an
unwanted constraint drop loses no data.

Not in scope: row-level security. Every ``tenant_id`` here is nullable, so none
of these tables meets the TEN2 precondition the RLS expand waves used.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260909_iso_absorb"
down_revision: Union[str, Sequence[str], None] = "20260908_soa_align"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

#: ``(table, column, length_before, length_after)``. Read off the model, then
#: verified against ``information_schema`` on a database at
#: ``20260908_soa_align``. Applied only when the column is still at
#: ``length_before``, so a re-run and an already-widened environment are both
#: no-ops.
WIDENED_COLUMNS: tuple[tuple[str, str, int, int], ...] = (
    ("information_assets", "criticality", 20, 50),
    ("information_assets", "status", 20, 50),
    ("information_security_risks", "status", 20, 50),
    ("information_security_risks", "threat_source", 100, 255),
    ("information_security_risks", "treatment_option", 30, 50),
    ("information_security_risks", "treatment_status", 30, 50),
    ("iso27001_controls", "effectiveness_rating", 20, 50),
    ("iso27001_controls", "implementation_status", 30, 50),
    ("security_incidents", "incident_type", 50, 100),
    ("security_incidents", "severity", 20, 50),
    ("security_incidents", "status", 30, 50),
    ("supplier_security_assessments", "assessment_type", 50, 100),
    ("supplier_security_assessments", "overall_rating", 30, 50),
    ("supplier_security_assessments", "risk_level", 20, 50),
    ("supplier_security_assessments", "status", 20, 50),
    ("supplier_security_assessments", "supplier_type", 50, 100),
)

#: ``(table, column, referent_table, referent_column, constraint_name)`` for the
#: seven foreign keys the models declare and the migrated schema does not have.
#: Every one is nullable and every one points at ``users``.
ADDED_FOREIGN_KEYS: tuple[tuple[str, str, str, str, str], ...] = (
    ("access_control_records", "user_id", "users", "id", "access_control_records_user_id_fkey"),
    ("information_assets", "owner_id", "users", "id", "information_assets_owner_id_fkey"),
    ("information_assets", "custodian_id", "users", "id", "information_assets_custodian_id_fkey"),
    ("information_security_risks", "risk_owner_id", "users", "id", "information_security_risks_risk_owner_id_fkey"),
    ("iso27001_controls", "control_owner_id", "users", "id", "iso27001_controls_control_owner_id_fkey"),
    ("security_incidents", "reported_by_id", "users", "id", "security_incidents_reported_by_id_fkey"),
    ("security_incidents", "assigned_to_id", "users", "id", "security_incidents_assigned_to_id_fkey"),
)

COMMENTED_TABLE = "iso27001_controls"
TABLE_COMMENT = "ISO 27001:2022 Annex A controls — composite unique enforced at DB level"


class OrphanedReferenceError(RuntimeError):
    """A foreign key cannot be created because rows point at a row that is gone."""


class ValuesTooLongError(RuntimeError):
    """A downgrade would have to truncate a value to narrow the column."""


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table: str) -> bool:
    return _inspector().has_table(table)


def _varchar_length(table: str, column: str) -> int | None:
    for reflected in _inspector().get_columns(table):
        if reflected["name"] == column:
            return getattr(reflected["type"], "length", None)
    return None


def _has_foreign_key(table: str, column: str) -> bool:
    return any(fk["constrained_columns"] == [column] for fk in _inspector().get_foreign_keys(table))


def _orphan_count(table: str, column: str, referent_table: str, referent_column: str) -> int:
    return (
        op.get_bind()
        .execute(
            sa.text(
                # Identifiers are module constants, never user input.
                f'SELECT count(*) FROM "{table}" child '  # noqa: S608
                f'WHERE child."{column}" IS NOT NULL AND NOT EXISTS ('
                f'SELECT 1 FROM "{referent_table}" parent '
                f'WHERE parent."{referent_column}" = child."{column}")'
            )
        )
        .scalar()
    )


def _resize(table: str, column: str, length_from: int, length_to: int) -> bool:
    """Change ``column`` to ``varchar(length_to)`` if it is still ``length_from``."""
    if _varchar_length(table, column) != length_from:
        return False
    op.alter_column(
        table,
        column,
        existing_type=sa.String(length=length_from),
        type_=sa.String(length=length_to),
        existing_nullable=_is_nullable(table, column),
    )
    return True


def _is_nullable(table: str, column: str) -> bool:
    for reflected in _inspector().get_columns(table):
        if reflected["name"] == column:
            return bool(reflected["nullable"])
    return True


def upgrade() -> None:
    widened: list[str] = []
    for table, column, before, after in WIDENED_COLUMNS:
        if not _has_table(table):
            logger.info("%s: no %r table, skipping widen of %s.", revision, table, column)
            continue
        if _resize(table, column, before, after):
            widened.append(f"{table}.{column} {before}->{after}")

    created: list[str] = []
    for table, column, referent_table, referent_column, name in ADDED_FOREIGN_KEYS:
        if not _has_table(table) or not _has_table(referent_table):
            logger.info("%s: no %r table, skipping foreign key on %s.", revision, table, column)
            continue
        if _has_foreign_key(table, column):
            continue
        orphans = _orphan_count(table, column, referent_table, referent_column)
        if orphans:
            # Refusing, not repairing. Nulling the column would discard the only
            # machine-readable link this row has to a person, and the alternative
            # -- creating the constraint NOT VALID -- reflects as a real foreign
            # key, so the next `alembic check` would call this drift resolved
            # when it is not.
            raise OrphanedReferenceError(
                f"{orphans} row(s) in {table}.{column} name a {referent_table} row that does not "
                f"exist, so {name} cannot be created. Decide what those rows should point at "
                f"(the {column.removesuffix('_id')}_name column beside it holds the recorded "
                "name); this migration will not null them for you."
            )
        op.create_foreign_key(
            name,
            table,
            referent_table,
            [column],
            [referent_column],
            ondelete="SET NULL",
        )
        created.append(name)

    if _has_table(COMMENTED_TABLE):
        op.create_table_comment(COMMENTED_TABLE, TABLE_COMMENT, existing_comment=None)

    logger.info(
        "%s: widened %d column(s) [%s]; created %d foreign key(s) [%s]; set the %s table comment.",
        revision,
        len(widened),
        ", ".join(widened) or "none",
        len(created),
        ", ".join(created) or "none",
        COMMENTED_TABLE,
    )


def downgrade() -> None:
    if _has_table(COMMENTED_TABLE):
        op.drop_table_comment(COMMENTED_TABLE, existing_comment=TABLE_COMMENT)

    for table, column, _referent_table, _referent_column, name in reversed(ADDED_FOREIGN_KEYS):
        if _has_table(table) and _has_foreign_key(table, column):
            op.drop_constraint(name, table, type_="foreignkey")

    for table, column, before, after in reversed(WIDENED_COLUMNS):
        if not _has_table(table) or _varchar_length(table, column) != after:
            continue
        too_long = (
            op.get_bind()
            .execute(
                sa.text(f'SELECT count(*) FROM "{table}" WHERE length("{column}") > :limit'),  # noqa: S608
                {"limit": before},
            )
            .scalar()
        )
        if too_long:
            raise ValuesTooLongError(
                f"{too_long} row(s) in {table}.{column} hold a value longer than {before} "
                "characters, so narrowing the column back would truncate it. Shorten or remove "
                "those values first; this downgrade will not discard them silently."
            )
        op.alter_column(
            table,
            column,
            existing_type=sa.String(length=after),
            type_=sa.String(length=before),
            existing_nullable=_is_nullable(table, column),
        )
