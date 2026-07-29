"""Add the ``created_by_id`` / ``updated_by_id`` columns eight tables never got.

Revision ID: 20260902_attrib_cols
Revises: 20260901_case_tenant_nn
Create Date: 2026-09-02

Why this exists
---------------
``AuditTrailMixin`` declares ``created_by_id`` and ``updated_by_id``. Eight
tables inherit it and the physical tables have neither column. SQLAlchemy emits
the full mapped column list for a whole-entity load, so this is not "a column
nobody reads is missing" — it makes the entire table unreadable through the ORM.
Every one of these raises ``UndefinedColumn`` on a plain ``select(Entity)``,
verified by executing it:

    auditor_profiles            AuditorProfile      GET  /auditor-competence/profiles/{user_id}
    capa_items                  CAPAItem            GET  /actions/, /rca-tools/capa/*
    fishbone_diagrams           FishboneDiagram     GET  /rca-tools/fishbone/*
    five_whys_analyses          FiveWhysAnalysis    GET  /rca-tools/five-whys/*
    legacy_key_risk_indicators  KeyRiskIndicator    GET  /kri, /executive-dashboard
    sla_configurations          SLAConfiguration    GET  /workflow/sla-configs
    workflow_rules              WorkflowRule        GET  /workflow/rules
    barrier_analyses            BarrierAnalysis     (no live read path)

``POST /api/v1/kri`` also assigns ``created_by_id=current_user.id`` and the PATCH
assigns ``updated_by_id``, so writes fail on the same column, not only reads.

Why the model is right and the database is wrong
-----------------------------------------------
Worth arguing rather than assuming, because the opposite conclusion — drop the
columns from the mixin — would also make the schema self-consistent.

All eight tables *do* carry ``created_by VARCHAR(100)`` and ``updated_by
VARCHAR(100)``, which no model declares. That looks like a rename left half
done, and it is not: the varchar holds a name, the integer holds a user id, and
they are different things. ``20260121_add_workflow_engine`` created
``workflow_rules`` with **both** — ``created_by_id INTEGER REFERENCES users(id)``
and ``created_by VARCHAR(100)`` — in the same ``create_table``. So id-based
attribution beside the legacy string is the intended design, 23 models already
declare ``ForeignKey("users.id")`` on ``created_by_id``, and 31 physical tables
already have the column. The eight here are the ones the pattern never reached.

What this migration does not do
-------------------------------
It does not backfill ``created_by_id`` from ``created_by``, and it does not drop
``created_by``. Resolving a free-text name against ``users`` is inference: names
are not unique, not required to match an account, and on these tables the value
may be a display name, a username or an email depending on which code wrote it.
Guessing wrong silently mis-attributes a governance record to a real person, and
#1398 settled the principle that a migration does not invent attribution. The
new columns therefore arrive NULL on every existing row, and ``created_by``
survives as the only attribution those rows have.

The foreign key is attached in the same ``ADD COLUMN``, which is safe without
any orphan check for the one reason that does not generalise: the column is new,
so every value in it is NULL, and NULL satisfies a foreign key. The 30 tables
that already *have* an unconstrained attribution column cannot be treated this
way and are handled separately, with an orphan scan, in
``20260902_attribution_fk``.

Reversibility
-------------
Fully reversible, and lossless in practice: ``downgrade`` drops columns that
``upgrade`` created empty and that nothing has had the chance to populate at the
point a downgrade is plausible. If rows have been written since, the downgrade
does discard those ids — noted here rather than guarded, because the alternative
is a downgrade that refuses, and every other downgrade in this chain is a plain
inverse.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260902_attrib_cols"
down_revision: Union[str, Sequence[str], None] = "20260901_case_tenant_nn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

#: Tables whose model inherits ``AuditTrailMixin`` and whose physical table is
#: missing one or both attribution columns. Measured from ``information_schema``
#: on a database at ``20260901_case_tenant_nn``, not read off the models.
#:
#: ``workflow_rules`` needs only ``updated_by_id``: its ``created_by_id`` was
#: created with the table, with a foreign key, by ``20260121_add_workflow_engine``.
TARGET_COLUMNS: dict[str, tuple[str, ...]] = {
    "auditor_profiles": ("created_by_id", "updated_by_id"),
    "barrier_analyses": ("created_by_id", "updated_by_id"),
    "capa_items": ("created_by_id", "updated_by_id"),
    "fishbone_diagrams": ("created_by_id", "updated_by_id"),
    "five_whys_analyses": ("created_by_id", "updated_by_id"),
    "legacy_key_risk_indicators": ("created_by_id", "updated_by_id"),
    "sla_configurations": ("created_by_id", "updated_by_id"),
    "workflow_rules": ("updated_by_id",),
}

ATTRIBUTION_TARGET = "users"


def _existing_columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    added: list[str] = []
    skipped: list[str] = []

    for table, columns in TARGET_COLUMNS.items():
        if not inspector.has_table(table):
            # A table absent from this database is not this migration's business:
            # the model/migration coverage gap it represents is tracked in
            # docs/governance/alembic_check_excluded_tables.md.
            skipped.append(f"{table} (no such table)")
            continue
        present = _existing_columns(table)
        for column in columns:
            if column in present:
                skipped.append(f"{table}.{column} (already present)")
                continue
            op.add_column(
                table,
                sa.Column(
                    column,
                    sa.Integer(),
                    sa.ForeignKey(f"{ATTRIBUTION_TARGET}.id", name=f"fk_{table}_{column}"),
                    nullable=True,
                ),
            )
            added.append(f"{table}.{column}")

    logger.info(
        "%s: added %d attribution column(s) [%s]; skipped %d [%s].",
        revision,
        len(added),
        ", ".join(added) or "none",
        len(skipped),
        ", ".join(skipped) or "none",
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table, columns in TARGET_COLUMNS.items():
        if not inspector.has_table(table):
            continue
        present = _existing_columns(table)
        for column in columns:
            if column not in present:
                continue
            # workflow_rules.created_by_id predates this revision, so it is not in
            # TARGET_COLUMNS and cannot be dropped here by construction.
            op.drop_column(table, column)
