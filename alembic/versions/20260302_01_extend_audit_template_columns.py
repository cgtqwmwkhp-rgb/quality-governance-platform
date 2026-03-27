"""Extend audit_templates and audit_questions with Workforce Development fields.

Revision ID: 20260302_wdp_cols
Revises: 20260227_audit_idx
Create Date: 2026-03-02 10:00:00.000000

Adds UUID external_id, template lifecycle status, subcategory, tags,
estimated_duration, pass_threshold to audit_templates.
Adds guidance, criticality, regulatory_reference, guidance_notes,
sign_off_required, assessor_guidance, training_materials,
failure_triggers_action to audit_questions.
Creates template_versions table for snapshot-based versioning.
"""

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260302_wdp_cols"
down_revision = "20260227_audit_idx"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_index(table_name: str, index_name: str) -> bool:
    return _inspector().has_table(table_name) and any(
        index["name"] == index_name for index in _inspector().get_indexes(table_name)
    )


def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    # -- audit_templates: new columns --
    op.add_column(
        "audit_templates",
        sa.Column("external_id", sa.String(36), nullable=True, unique=True, index=True),
    )
    op.add_column(
        "audit_templates",
        sa.Column(
            "template_status",
            sa.String(50),
            nullable=False,
            server_default="published",
        ),
    )
    op.add_column(
        "audit_templates",
        sa.Column("subcategory", sa.String(100), nullable=True),
    )
    op.add_column(
        "audit_templates",
        sa.Column("tags_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "audit_templates",
        sa.Column("estimated_duration", sa.Integer(), nullable=True),
    )
    op.add_column(
        "audit_templates",
        sa.Column("pass_threshold", sa.Float(), nullable=True),
    )

    # Backfill external_id for existing rows
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id FROM audit_templates WHERE external_id IS NULL")
    ).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE audit_templates SET external_id = :uid WHERE id = :tid"),
            {"uid": str(uuid.uuid4()), "tid": row[0]},
        )

    if dialect != "sqlite":
        op.alter_column("audit_templates", "external_id", nullable=False)

    # -- audit_questions: new columns --
    op.add_column(
        "audit_questions",
        sa.Column("guidance", sa.Text(), nullable=True),
    )
    op.add_column(
        "audit_questions",
        sa.Column("criticality", sa.String(50), nullable=True),
    )
    op.add_column(
        "audit_questions",
        sa.Column("regulatory_reference", sa.String(200), nullable=True),
    )
    op.add_column(
        "audit_questions",
        sa.Column("guidance_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "audit_questions",
        sa.Column("sign_off_required", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "audit_questions",
        sa.Column("assessor_guidance_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "audit_questions",
        sa.Column("training_materials_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "audit_questions",
        sa.Column("failure_triggers_action", sa.Boolean(), nullable=False, server_default="false"),
    )

    # -- template_versions table --
    op.create_table(
        "template_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("audit_templates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("template_versions")

    op.drop_column("audit_questions", "failure_triggers_action")
    op.drop_column("audit_questions", "training_materials_json")
    op.drop_column("audit_questions", "assessor_guidance_json")
    op.drop_column("audit_questions", "sign_off_required")
    op.drop_column("audit_questions", "guidance_notes")
    op.drop_column("audit_questions", "regulatory_reference")
    op.drop_column("audit_questions", "criticality")
    op.drop_column("audit_questions", "guidance")

    op.drop_column("audit_templates", "pass_threshold")
    op.drop_column("audit_templates", "estimated_duration")
    op.drop_column("audit_templates", "tags_json")
    op.drop_column("audit_templates", "subcategory")
    op.drop_column("audit_templates", "template_status")
    if _has_index("audit_templates", "ix_audit_templates_external_id"):
        op.drop_index("ix_audit_templates_external_id", table_name="audit_templates")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("audit_templates") as batch_op:
            batch_op.drop_column("external_id")
    else:
        op.drop_column("audit_templates", "external_id")
