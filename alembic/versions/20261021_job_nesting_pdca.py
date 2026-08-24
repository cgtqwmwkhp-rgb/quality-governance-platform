"""JL-UX-W2: job cycle nesting link kind + PDCA phase on steps.

Revision ID: 20261021_job_nest_pdca
Revises: 20261020_job_cell_links
Create Date: 2026-10-21

Additive. Three changes, all on tables the JL chain already created:

1. ``ck_job_cell_links_kind`` gains ``job_cycle`` so a cell can nest another
   JobType. Nesting is generic (any JobType → any other JobType) — there is no
   hardcoded Operational↔Engineer pair.
2. ``job_cell_links.target_job_type_id`` — nullable FK to ``job_types``, set
   only for ``kind='job_cycle'``. This is the *only* SSOT for nesting; lanes
   grow no parallel FK, and the lane nest chip is derived from these links.
3. ``job_steps.pdca_phase`` — nullable ``plan|do|check|act`` annotation used
   for step colouring. Nullable because most existing steps have no phase and
   inventing one would be a data claim this migration cannot make.

No RLS changes: both tables were already hardened (``job_cell_links`` by
20261020, ``job_steps`` by 20261019) and no new table is introduced.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261021_job_nest_pdca"
down_revision: Union[str, Sequence[str], None] = "20261020_job_cell_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

KIND_CONSTRAINT = "ck_job_cell_links_kind"
KIND_VALUES_AFTER = "kind IN ('app', 'external', 'audit_outcome', 'job_cycle')"
KIND_VALUES_BEFORE = "kind IN ('app', 'external', 'audit_outcome')"

PDCA_CONSTRAINT = "ck_job_steps_pdca_phase"
PDCA_VALUES = "pdca_phase IS NULL OR pdca_phase IN ('plan', 'do', 'check', 'act')"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(col["name"] == column_name for col in _inspector().get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(idx["name"] == index_name for idx in _inspector().get_indexes(table_name))


def _replace_check_constraint(table: str, name: str, condition: str) -> None:
    """Swap a named CHECK for a wider one.

    SQLite cannot ALTER a constraint, so the batch helper rebuilds the table;
    PostgreSQL drops and recreates in place. ``IF EXISTS`` on the drop keeps
    this idempotent and tolerant of a schema built by ``create_all`` (where the
    constraint may carry no name at all).
    """
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            try:
                batch_op.drop_constraint(name, type_="check")
            except Exception:  # noqa: BLE001 — unnamed/absent CHECK on rebuilt table
                logger.info("%s: no existing %s to drop on sqlite", revision, name)
            batch_op.create_check_constraint(name, condition)
        return
    op.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"))
    op.create_check_constraint(name, table, condition)


def upgrade() -> None:
    if not _table_exists("job_cell_links"):
        logger.warning("%s: job_cell_links missing — nesting columns skipped", revision)
    else:
        if not _column_exists("job_cell_links", "target_job_type_id"):
            op.add_column(
                "job_cell_links",
                sa.Column("target_job_type_id", sa.Integer(), nullable=True),
            )
            # CASCADE, not SET NULL: a job_cycle link with no target cannot
            # resolve an href, so the link must not outlive its target.
            op.create_foreign_key(
                "fk_job_cell_links_target_job_type",
                "job_cell_links",
                "job_types",
                ["target_job_type_id"],
                ["id"],
                ondelete="CASCADE",
            )
        if not _index_exists("job_cell_links", "ix_job_cell_links_tenant_target_type"):
            op.create_index(
                "ix_job_cell_links_tenant_target_type",
                "job_cell_links",
                ["tenant_id", "target_job_type_id"],
            )
        _replace_check_constraint("job_cell_links", KIND_CONSTRAINT, KIND_VALUES_AFTER)

    if not _table_exists("job_steps"):
        logger.warning("%s: job_steps missing — pdca_phase skipped", revision)
        return
    if not _column_exists("job_steps", "pdca_phase"):
        op.add_column("job_steps", sa.Column("pdca_phase", sa.String(length=16), nullable=True))
    _replace_check_constraint("job_steps", PDCA_CONSTRAINT, PDCA_VALUES)


def downgrade() -> None:
    if _table_exists("job_steps"):
        bind = op.get_bind()
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("job_steps") as batch_op:
                batch_op.drop_constraint(PDCA_CONSTRAINT, type_="check")
        else:
            op.execute(sa.text(f"ALTER TABLE job_steps DROP CONSTRAINT IF EXISTS {PDCA_CONSTRAINT}"))
        if _column_exists("job_steps", "pdca_phase"):
            op.drop_column("job_steps", "pdca_phase")

    if not _table_exists("job_cell_links"):
        return
    # Rows using the widened kind would violate the narrow CHECK on the way back.
    op.execute(sa.text("DELETE FROM job_cell_links WHERE kind = 'job_cycle'"))
    _replace_check_constraint("job_cell_links", KIND_CONSTRAINT, KIND_VALUES_BEFORE)
    if _index_exists("job_cell_links", "ix_job_cell_links_tenant_target_type"):
        op.drop_index("ix_job_cell_links_tenant_target_type", table_name="job_cell_links")
    if _column_exists("job_cell_links", "target_job_type_id"):
        bind = op.get_bind()
        if bind.dialect.name != "sqlite":
            op.execute(
                sa.text(
                    "ALTER TABLE job_cell_links "
                    "DROP CONSTRAINT IF EXISTS fk_job_cell_links_target_job_type"
                )
            )
        op.drop_column("job_cell_links", "target_job_type_id")
