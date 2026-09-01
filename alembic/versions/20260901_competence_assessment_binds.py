"""Assessment binds + demonstration overlay (CB-PR4).

Revision ID: 20260901_comp_bind
Revises: 20260901_comp_cr

An explicit template → PAMS characteristic bind, and the demonstration rows a
completed assessment writes against it. QGP never writes PAMS; a failed
demonstration opens a change request instead of deleting issuance.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_comp_bind"
down_revision: Union[str, Sequence[str], None] = "20260901_comp_cr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if not _has_table("competence_assessment_binds"):
        op.create_table(
            "competence_assessment_binds",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("template_id", sa.Integer(), nullable=False),
            sa.Column("characteristic_key", sa.String(length=80), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["template_id"], ["audit_templates.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "template_id", name="uq_competence_assessment_binds_template"),
            sa.UniqueConstraint(
                "tenant_id",
                "characteristic_key",
                name="uq_competence_assessment_binds_characteristic",
            ),
        )
        op.create_index("ix_competence_assessment_binds_tenant_id", "competence_assessment_binds", ["tenant_id"])

    if not _has_table("competence_demonstrations"):
        op.create_table(
            "competence_demonstrations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("engineer_id", sa.Integer(), nullable=False),
            sa.Column("characteristic_key", sa.String(length=80), nullable=False),
            sa.Column("template_id", sa.Integer(), nullable=False),
            sa.Column("source_run_id", sa.String(length=36), nullable=False),
            sa.Column("outcome", sa.String(length=50), nullable=False),
            sa.Column("state", sa.String(length=32), nullable=False),
            sa.Column("assessed_at", sa.DateTime(), nullable=False),
            sa.Column("assessed_by_id", sa.Integer(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_run_id", name="uq_competence_demonstrations_source_run"),
        )
        op.create_index("ix_competence_demonstrations_tenant_id", "competence_demonstrations", ["tenant_id"])
        op.create_index("ix_competence_demonstrations_engineer_id", "competence_demonstrations", ["engineer_id"])
        op.create_index(
            "ix_competence_demonstrations_cell",
            "competence_demonstrations",
            ["tenant_id", "engineer_id", "characteristic_key"],
        )


def downgrade() -> None:
    if _has_table("competence_demonstrations"):
        op.drop_index("ix_competence_demonstrations_cell", table_name="competence_demonstrations")
        op.drop_index("ix_competence_demonstrations_engineer_id", table_name="competence_demonstrations")
        op.drop_index("ix_competence_demonstrations_tenant_id", table_name="competence_demonstrations")
        op.drop_table("competence_demonstrations")
    if _has_table("competence_assessment_binds"):
        op.drop_index("ix_competence_assessment_binds_tenant_id", table_name="competence_assessment_binds")
        op.drop_table("competence_assessment_binds")
