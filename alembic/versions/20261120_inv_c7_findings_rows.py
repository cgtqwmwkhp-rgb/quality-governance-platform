"""INV-C7 — findings become rows instead of one paragraph.

Revision ID: 20261120_inv_c7_findings
Revises: 20260903_asm_plant_evid

The parent is **not** the numerically-latest filename in ``alembic/versions``.
``20261119_aud_f5_response_evidence`` sorts last and is not the head: the
competence-board revisions are filed as ``20260901_*`` / ``20260903_*`` while
chaining *after* the higher-numbered files, so the real tip is
``20260903_asm_plant_evid`` (CB-UI-3 plant evidence). Revising the file that
looks latest would fork the chain, and a second head makes
``alembic upgrade head`` refuse on deploy rather than at review.
``test_the_new_revision_is_the_only_head`` computes this rather than trusting
the filenames.

ADD TABLE only. No existing column is altered, nothing is dropped and no row is
rewritten, so this is safe to run while investigations are being edited. The
expand half of expand/contract: ``investigation_runs.data`` keeps its
``findings`` string (flat and nested), which is still what the closure gate and
the pack read. Dropping that string is a later contraction (INV-C8 moves the
gate onto rows, INV-C18 drops the flat readers) and is deliberately not here.

**No backfill, deliberately.** Converting the legacy ``findings`` string into
rows needs the split rule in
``src/domain/services/investigation_findings_service.py``, and applying it to
every run in the database would be a full scan plus a write per run, holding
rows that the workspace is saving into. It is done lazily instead: the first
list or write for a run converts that run's string under a row lock on the run,
and only when the run has no rows yet. A run nobody opens is never touched and
loses nothing — its string is still read by every existing caller.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261120_inv_c7_findings"
down_revision: Union[str, Sequence[str], None] = "20260903_asm_plant_evid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "investigation_findings"


def _table_exists() -> bool:
    return sa.inspect(op.get_bind()).has_table(TABLE)


def upgrade() -> None:
    if _table_exists():
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # NOT NULL from the first day this table exists: there is no history to
        # migrate, so the WCS-TEN2 backfill-then-maybe-tighten idiom (and the
        # drift it caused) does not apply here.
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("investigation_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # A finding cannot outlive the investigation it belongs to.
        sa.ForeignKeyConstraint(["investigation_id"], ["investigation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investigation_findings_tenant_id", TABLE, ["tenant_id"])
    op.create_index("ix_investigation_findings_investigation_id", TABLE, ["investigation_id"])
    op.create_index("ix_investigation_findings_created_at", TABLE, ["created_at"])
    # The only read this table serves: one run's findings, in order.
    op.create_index("ix_investigation_findings_run_order", TABLE, ["investigation_id", "sort_order", "id"])


def downgrade() -> None:
    """Drop the table.

    Safe because nothing outside this table depends on it: the ``findings``
    string in ``investigation_runs.data`` is kept in step with the rows on every
    write, so a downgrade loses the row structure (order and per-finding ids)
    and keeps the text the closure gate and the pack actually read.
    """
    if _table_exists():
        op.drop_table(TABLE)
