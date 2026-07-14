"""Assessor competence_gap → Workforce closed loop.

Revision ID: 20260714_comp_gap
Revises: 20260713_op_assess
Create Date: 2026-07-14

- Creates competence_gap_actions (idempotent source unique)
- Adds CAPASource.competence_gap enum value
- Does NOT create training_tickets (owned by path11/workforce-p0-spine)
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_comp_gap"
down_revision: Union[str, Sequence[str], None] = "20260713_op_assess"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'capasource'")).fetchone()
        if result:
            try:
                op.execute("ALTER TYPE capasource ADD VALUE IF NOT EXISTS 'competence_gap'")
            except Exception:
                pass

    op.create_table(
        "competence_gap_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=30), nullable=False),
        sa.Column("engineer_id", sa.Integer(), nullable=True),
        sa.Column("requirement_id", sa.Integer(), nullable=True),
        sa.Column("ticket_scheme", sa.String(length=100), nullable=True),
        sa.Column("capa_action_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "signal_type IN ('competence_gap', 'nonconformity')",
            name="ck_competence_gap_signal_type",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'linked', 'capa_created', 'resolved', 'dismissed')",
            name="ck_competence_gap_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["engineer_id"], ["engineers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requirement_id"], ["competency_requirements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["capa_action_id"], ["capa_actions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "source_type", "source_id", name="uq_competence_gap_tenant_source"),
    )
    op.create_index("ix_competence_gap_actions_tenant_id", "competence_gap_actions", ["tenant_id"])
    op.create_index("ix_competence_gap_tenant_status", "competence_gap_actions", ["tenant_id", "status"])
    op.create_index("ix_competence_gap_engineer", "competence_gap_actions", ["engineer_id"])
    op.create_index("ix_competence_gap_capa", "competence_gap_actions", ["capa_action_id"])


def downgrade() -> None:
    op.drop_index("ix_competence_gap_capa", table_name="competence_gap_actions")
    op.drop_index("ix_competence_gap_engineer", table_name="competence_gap_actions")
    op.drop_index("ix_competence_gap_tenant_status", table_name="competence_gap_actions")
    op.drop_index("ix_competence_gap_actions_tenant_id", table_name="competence_gap_actions")
    op.drop_table("competence_gap_actions")
    # Postgres enum value 'competence_gap' is irreversible — leave in place.
