"""Add CAPA (Corrective and Preventive Action) table.

Revision ID: 20260220_capa_actions
Revises: 20260220_perf_indexes
Create Date: 2026-02-20 18:00:00.000000

Creates the capa_actions table for tracking corrective and preventive actions
across the quality management system.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260220_capa_actions"
down_revision: Union[str, None] = "20260220_perf_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    op.create_table(
        "capa_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reference_number", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "capa_type",
            sa.Enum("corrective", "preventive", name="capatype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("open", "in_progress", "verification", "closed", "overdue", name="capastatus"),
            server_default="open",
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum("low", "medium", "high", "critical", name="capapriority"),
            server_default="medium",
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.Enum(
                "incident", "audit_finding", "complaint", "ncr", "risk", "management_review",
                name="capasource",
            ),
            nullable=True,
        ),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("proposed_action", sa.Text(), nullable=True),
        sa.Column("verification_method", sa.Text(), nullable=True),
        sa.Column("verification_result", sa.Text(), nullable=True),
        sa.Column("effectiveness_criteria", sa.Text(), nullable=True),
        sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("iso_standard", sa.String(50), nullable=True),
        sa.Column("clause_reference", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_capa_actions_reference_number", "capa_actions", ["reference_number"], unique=True)
    op.create_index("ix_capa_actions_status", "capa_actions", ["status"])
    op.create_index("ix_capa_actions_tenant_id", "capa_actions", ["tenant_id"])


def downgrade() -> None:
    if _has_index("capa_actions", "ix_capa_actions_tenant_id"):
        op.drop_index("ix_capa_actions_tenant_id", table_name="capa_actions")
    if _has_index("capa_actions", "ix_capa_actions_status"):
        op.drop_index("ix_capa_actions_status", table_name="capa_actions")
    if _has_index("capa_actions", "ix_capa_actions_reference_number"):
        op.drop_index("ix_capa_actions_reference_number", table_name="capa_actions")
    if sa.inspect(op.get_bind()).has_table("capa_actions"):
        op.drop_table("capa_actions")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS capasource")
        op.execute("DROP TYPE IF EXISTS capapriority")
        op.execute("DROP TYPE IF EXISTS capastatus")
        op.execute("DROP TYPE IF EXISTS capatype")
