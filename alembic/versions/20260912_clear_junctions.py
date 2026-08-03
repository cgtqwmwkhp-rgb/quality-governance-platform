"""Empty the alembic check exclusion register: drop six dead junctions, name the escalation table (C-24).

Revision ID: 20260912_clear_junctions
Revises: 20260911_shared_severity
Create Date: 2026-09-12

What was wrong
--------------
Eight names were left on ``_ALEMBIC_CHECK_EXCLUDED_TABLES`` after
``20260909_iso_absorb``, carrying 23 autogenerate operations that no gate
reported, because ``include_object`` removes a table from the comparison before
a single column of it is looked at. Measured on PostgreSQL 16.14 against a
database built by ``alembic upgrade head`` at ``20260911_shared_severity``:

    audit_finding_clause_mapping   DropTableOp 1, DropIndexOp 2
    audit_section_clause_mapping   DropTableOp 1, DropIndexOp 2
    risk_audit_mapping             DropTableOp 1, DropIndexOp 2
    risk_clause_mapping            DropTableOp 1, DropIndexOp 2
    risk_control_mapping           DropTableOp 1, DropIndexOp 2
    risk_incident_mapping          DropTableOp 1, DropIndexOp 2
    escalation_rules_config        DropTableOp 1, DropIndexOp 1
    escalation_rules               CreateTableOp 1, CreateIndexOp 2

Unlike every previous entry cleared under C-24, none of this is a column-shape
disagreement. It is two different problems, and neither is fixed by converging a
model with a table.

Part 1 -- six junction tables nothing reads
--------------------------------------------
``20260220_normalize_json`` created six junction tables to replace JSON array
columns, copied the arrays into them, and renamed the source columns with a
``_legacy`` suffix. The second half of that plan never happened: no SQLAlchemy
model was ever written for any of the six, no service or route names them, and
the application still reads the ``_legacy`` JSON columns it was supposed to stop
reading. ``Risk.clause_ids_json_legacy`` is mapped and read; ``risk_clause_mapping``
is not mapped at all.

So the rows in them are a **six-month-old derived copy** of data whose source is
still present and still authoritative. They are not a second record of anything:
every row was computed from ``risks.clause_ids_json``,
``risks.control_ids_json``, ``risks.linked_audit_ids_json``,
``risks.linked_incident_ids_json`` or ``audit_findings.clause_ids_json`` at the
moment ``20260220_normalize_json`` ran, those columns are the ones the
application has written to ever since, and nothing has updated the junctions.
``audit_section_clause_mapping`` never had a source column and has never held a
row anywhere.

Dropping them is therefore not a data decision, it is removing a stale copy --
and the upgrade logs the row count of each table before it goes, so the deploy
log records exactly what was discarded rather than asking anyone to take that on
trust. ``downgrade`` recreates all six in their original shape and re-derives
their contents from the same ``_legacy`` columns with the same SQL
``20260220_normalize_json`` used, which is what makes this reversible: the source
of every dropped row is still in the database.

Not renamed to a normalized design instead, deliberately. Doing that properly
means models, a migration for the ``_legacy`` reads in
``src/domain/models/risk.py`` and ``audit_service.py``, and an API contract
change on ``clause_ids`` / ``control_ids``; that is the work
``docs/data/json-column-reduction.md`` describes and it is not this PR. What this
PR settles is that the half-finished attempt should not keep a gate muted while
it waits.

Part 2 -- a model that named a table which does not exist
---------------------------------------------------------
``20260220_workflow_persist`` created ``escalation_rules_config``.
``src/domain/models/workflow.py`` declared ``EscalationRule.__tablename__ =
"escalation_rules"``. Both names went on the exclusion register -- one as a table
with no model, the other as a model with no table -- which is a single mismatch
recorded twice and deferred as though it were two problems.

The model is the side that was wrong, and it was not merely differently named:
``select(EscalationRule)`` would have raised ``UndefinedTable`` on every migrated
database since February. Nothing raised, because nothing queries it -- the
escalation logic in ``workflow_service.py`` uses an in-memory ``EscalationRule``
``Enum`` of the same name and never touches this table. So pointing
``__tablename__`` at ``escalation_rules_config`` cannot break a caller: there is
no caller. It makes the class usable for the first time, and it makes
``escalation_logs.rule_id`` reference the table the physical foreign key has
always pointed at.

Three columns then have to converge for the table to compare to zero, and this
migration is the database side of it.

* ``tenant_id`` -- declared by the model, absent from the table, added here
  nullable with its foreign key and index. This is the only ``AddColumnOp`` in
  the repository and the class ``scripts/validate_alembic_drift_ratchet.py``
  fails on unconditionally, so it could not be left: a declared column the
  database lacks makes the whole table unreadable to ``select(Model)``, which is
  precisely the state ``escalation_rules_config`` would have been left in the
  moment the rename made the class reachable.

* ``trigger_unit``, ``send_notification``, ``is_active`` -- the model declares
  all three ``NOT NULL``, the table has them nullable with a server default
  (``'hours'``, ``true``, ``true``). The *database* moves, because here that is
  the move that cannot reject data: the server default already guarantees a
  value on every row inserted without one, so the only row ``SET NOT NULL``
  could reject is one where a NULL was written explicitly -- and nothing has
  ever written to this table at all. Any such row is repaired to the column's
  own server default first, and the count is logged rather than assumed to be
  zero. The alternative, making the model ``Optional``, would ship a nullable
  boolean flag on a table that is about to have its first reader.

Not in scope: row-level security. ``tenant_id`` arrives nullable because that is
what the model declares, so this table does not meet the TEN2 precondition the
RLS expand waves used, and there is no parent row to derive a tenant from.

Not in scope either: ``escalation_logs.tenant_id`` has no foreign key to
``tenants`` although the model declares one. That is one of the 103
``CreateForeignKeyOp`` the operation-type filter suppresses repository-wide, it
predates this work, and fixing one instance of it here would not change the
gate. It is left recorded in the baseline.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260912_clear_junctions"
down_revision: Union[str, Sequence[str], None] = "20260911_shared_severity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

ESCALATION_TABLE = "escalation_rules_config"
TENANT_COLUMN = "tenant_id"
TENANT_INDEX = f"ix_{ESCALATION_TABLE}_{TENANT_COLUMN}"
TENANT_FK = f"fk_{ESCALATION_TABLE}_{TENANT_COLUMN}"

#: Columns ``EscalationRule`` declares ``NOT NULL`` that the table has nullable,
#: with the server default the table already carries for each. The default is
#: restated rather than read from the catalogue so the value a repaired row gets
#: is reviewable here.
NOT_NULL_COLUMNS: tuple[tuple[str, str], ...] = (
    ("trigger_unit", "'hours'"),
    ("send_notification", "true"),
    ("is_active", "true"),
)

#: The six junction tables ``20260220_normalize_json`` created, with the two
#: foreign key columns and unique constraint name each was created with, so
#: ``downgrade`` rebuilds the shape rather than an approximation of it. The
#: ``source`` entry is the ``(table, id column, legacy JSON column)`` the rows
#: were derived from; ``None`` for the one that never had a source.
JUNCTIONS: tuple[dict, ...] = (
    {
        "table": "risk_clause_mapping",
        "left": ("risk_id", "risks.id"),
        "right": ("clause_id", "clauses.id"),
        "unique": "uq_risk_clause",
        "source": ("risks", "id", "clause_ids_json_legacy"),
    },
    {
        "table": "risk_control_mapping",
        "left": ("risk_id", "risks.id"),
        "right": ("control_id", "controls.id"),
        "unique": "uq_risk_control",
        "source": ("risks", "id", "control_ids_json_legacy"),
    },
    {
        "table": "risk_audit_mapping",
        "left": ("risk_id", "risks.id"),
        "right": ("audit_id", "audit_runs.id"),
        "unique": "uq_risk_audit",
        "source": ("risks", "id", "linked_audit_ids_json_legacy"),
    },
    {
        "table": "risk_incident_mapping",
        "left": ("risk_id", "risks.id"),
        "right": ("incident_id", "incidents.id"),
        "unique": "uq_risk_incident",
        "source": ("risks", "id", "linked_incident_ids_json_legacy"),
    },
    {
        "table": "audit_finding_clause_mapping",
        "left": ("finding_id", "audit_findings.id"),
        "right": ("clause_id", "clauses.id"),
        "unique": "uq_finding_clause",
        "source": ("audit_findings", "id", "clause_ids_json_legacy"),
    },
    {
        "table": "audit_section_clause_mapping",
        "left": ("section_id", "audit_sections.id"),
        "right": ("clause_id", "clauses.id"),
        "unique": "uq_section_clause",
        "source": None,
    },
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _columns(table: str) -> dict[str, dict]:
    return {column["name"]: column for column in _inspector().get_columns(table)}


def _has_index(table: str, name: str) -> bool:
    return any(index["name"] == name for index in _inspector().get_indexes(table))


def _row_count(table: str) -> int:
    query = f'SELECT count(*) FROM "{table}"'  # noqa: S608 - table names come from JUNCTIONS, never a request
    return op.get_bind().execute(sa.text(query)).scalar() or 0


# --------------------------------------------------------------------------- #
# Part 1: the six junction tables                                             #
# --------------------------------------------------------------------------- #


def _drop_junctions() -> None:
    inspector = _inspector()
    dropped: list[str] = []
    absent: list[str] = []
    for junction in JUNCTIONS:
        table = junction["table"]
        if not inspector.has_table(table):
            absent.append(table)
            continue
        # Counted before the drop so the deploy log, not this docstring, is the
        # record of what each environment actually discarded.
        rows = _row_count(table)
        source = junction["source"]
        logger.info(
            "%s: dropping %s (%d row(s)); source of record remains %s.",
            revision,
            table,
            rows,
            f"{source[0]}.{source[2]}" if source else "nothing -- it never had a source column",
        )
        op.drop_table(table)
        dropped.append(table)
    logger.info(
        "%s: dropped %d junction table(s) [%s]; %d already absent [%s].",
        revision,
        len(dropped),
        ", ".join(dropped) or "none",
        len(absent),
        ", ".join(absent) or "none",
    )


def _recreate_junctions() -> None:
    """Rebuild the six tables in the shape ``20260220_normalize_json`` created."""
    inspector = _inspector()
    for junction in JUNCTIONS:
        table = junction["table"]
        if inspector.has_table(table):
            continue
        left_column, left_reference = junction["left"]
        right_column, right_reference = junction["right"]
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(left_column, sa.Integer(), nullable=False),
            sa.Column(right_column, sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint([left_column], [left_reference], ondelete="CASCADE"),
            sa.ForeignKeyConstraint([right_column], [right_reference], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(left_column, right_column, name=junction["unique"]),
        )
        op.create_index(f"ix_{table}_{left_column}", table, [left_column])
        op.create_index(f"ix_{table}_{right_column}", table, [right_column])

        source = junction["source"]
        if source is None:
            continue
        source_table, source_id, source_json = source
        if source_json not in _columns(source_table):
            # The ``_legacy`` rename is two revisions of history away from this
            # one; if it is not there the rows cannot be re-derived, and an empty
            # table is a better downgrade than a failed one.
            logger.warning(
                "%s: %s.%s is absent, so %s is recreated empty.",
                revision,
                source_table,
                source_json,
                table,
            )
            continue
        rederive = f"""
            INSERT INTO {table} ({left_column}, {right_column})
            SELECT src.{source_id}, CAST(je.value AS INTEGER)
            FROM {source_table} AS src,
                 json_array_elements_text(src.{source_json}) AS je(value)
            WHERE src.{source_json} IS NOT NULL
              AND CAST(src.{source_json} AS TEXT) NOT IN ('[]', 'null')
            ON CONFLICT DO NOTHING
        """  # noqa: S608 - every identifier comes from JUNCTIONS; this is 20260220_normalize_json's own SQL
        op.execute(sa.text(rederive))
        logger.info("%s: recreated %s with %d re-derived row(s).", revision, table, _row_count(table))


# --------------------------------------------------------------------------- #
# Part 2: escalation_rules_config                                             #
# --------------------------------------------------------------------------- #


def _add_tenant_column() -> None:
    if TENANT_COLUMN in _columns(ESCALATION_TABLE):
        # Adopted without verifying its shape, the trade 20260908_soa_align made
        # and for the same reason: from this revision the table is compared by
        # `alembic check`, so a mis-shaped adoption is reported on the next run
        # rather than hidden.
        logger.info("%s: %s.%s already present, adopted unverified.", revision, ESCALATION_TABLE, TENANT_COLUMN)
    else:
        op.add_column(
            ESCALATION_TABLE,
            sa.Column(
                TENANT_COLUMN,
                sa.Integer(),
                sa.ForeignKey("tenants.id", name=TENANT_FK),
                nullable=True,
            ),
        )
    if not _has_index(ESCALATION_TABLE, TENANT_INDEX):
        op.create_index(TENANT_INDEX, ESCALATION_TABLE, [TENANT_COLUMN])


def _enforce_not_null() -> None:
    """Converge the three columns the model declares ``NOT NULL``.

    Unconditional, not data-conditional: any NULL is repaired to the column's
    own server default first, so there is no row the ``SET NOT NULL`` can reject
    and no outcome that depends on what the table happens to hold. That is what
    ``tests/unit/test_migration_schema_drift_lint.py`` asks for -- a migration
    whose nullability outcome varies with row data has to be able to fail, and
    this one's does not vary.
    """
    present = _columns(ESCALATION_TABLE)
    for column, default in NOT_NULL_COLUMNS:
        if column not in present:
            logger.warning("%s: %s.%s is absent; nothing to tighten.", revision, ESCALATION_TABLE, column)
            continue
        if not present[column]["nullable"]:
            continue
        # noqa: S608 below -- the column name and the default are both module
        # constants from NOT_NULL_COLUMNS, and the default is restated there so
        # the value a repaired row receives is reviewable rather than reflected.
        repair = f'UPDATE "{ESCALATION_TABLE}" SET "{column}" = {default} WHERE "{column}" IS NULL'  # noqa: S608
        repaired = op.get_bind().execute(sa.text(repair))
        op.alter_column(ESCALATION_TABLE, column, nullable=False)
        logger.info(
            "%s: %s.%s set NOT NULL; %d row(s) repaired to %s.",
            revision,
            ESCALATION_TABLE,
            column,
            repaired.rowcount,
            default,
        )


def _relax_not_null() -> None:
    present = _columns(ESCALATION_TABLE)
    for column, _default in NOT_NULL_COLUMNS:
        if column in present and not present[column]["nullable"]:
            op.alter_column(ESCALATION_TABLE, column, nullable=True)


def _drop_tenant_column() -> None:
    if _has_index(ESCALATION_TABLE, TENANT_INDEX):
        op.drop_index(TENANT_INDEX, table_name=ESCALATION_TABLE)
    if TENANT_COLUMN in _columns(ESCALATION_TABLE):
        op.drop_column(ESCALATION_TABLE, TENANT_COLUMN)


# --------------------------------------------------------------------------- #
# Entry points                                                                #
# --------------------------------------------------------------------------- #


def upgrade() -> None:
    _drop_junctions()

    if not _inspector().has_table(ESCALATION_TABLE):
        # Nothing to converge, and nothing this migration can do about it: the
        # table is created by 20260220_workflow_persist, so a database without it
        # has a chain problem that predates this revision.
        logger.warning("%s: no %r table; skipping the escalation convergence.", revision, ESCALATION_TABLE)
        return

    _add_tenant_column()
    _enforce_not_null()


def downgrade() -> None:
    if _inspector().has_table(ESCALATION_TABLE):
        _relax_not_null()
        _drop_tenant_column()
    _recreate_junctions()
