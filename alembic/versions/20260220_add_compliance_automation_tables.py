"""Add compliance automation tables.

Revision ID: 20260220_compliance_auto
Revises: 20260220_compliance_evidence
Create Date: 2026-02-20 12:00:00.000000

Creates tables for:
- regulatory_updates
- gap_analyses
- certificates
- scheduled_audits
- compliance_scores
- riddor_submissions
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260220_compliance_auto"
down_revision: Union[str, None] = "20260220_compliance_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "regulatory_updates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(50), nullable=False, index=True),
        sa.Column("source_reference", sa.String(100), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("impact", sa.String(20), server_default="medium"),
        sa.Column("affected_standards", sa.JSON(), nullable=True),
        sa.Column("affected_clauses", sa.JSON(), nullable=True),
        sa.Column("published_date", sa.DateTime(), nullable=False),
        sa.Column("effective_date", sa.DateTime(), nullable=True),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("is_reviewed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("requires_action", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("action_notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "gap_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("regulatory_update_id", sa.Integer(), sa.ForeignKey("regulatory_updates.id"), nullable=True, index=True),
        sa.Column("standard_id", sa.Integer(), sa.ForeignKey("standards.id"), nullable=True, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("gaps", sa.JSON(), nullable=False),
        sa.Column("total_gaps", sa.Integer(), server_default="0"),
        sa.Column("critical_gaps", sa.Integer(), server_default="0"),
        sa.Column("high_gaps", sa.Integer(), server_default="0"),
        sa.Column("recommendations", sa.JSON(), nullable=True),
        sa.Column("estimated_effort_hours", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("assigned_to", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("certificate_type", sa.String(50), nullable=False, index=True),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False, index=True),
        sa.Column("entity_name", sa.String(255), nullable=True),
        sa.Column("issuing_body", sa.String(255), nullable=True),
        sa.Column("issue_date", sa.DateTime(), nullable=False),
        sa.Column("expiry_date", sa.DateTime(), nullable=False, index=True),
        sa.Column("reminder_days", sa.Integer(), server_default="30"),
        sa.Column("reminder_sent", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("reminder_sent_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(50), server_default="valid"),
        sa.Column("is_critical", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("document_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "scheduled_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("audit_type", sa.String(50), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("audit_templates.id"), nullable=True),
        sa.Column("frequency", sa.String(50), nullable=False),
        sa.Column("schedule_config", sa.JSON(), nullable=True),
        sa.Column("next_due_date", sa.DateTime(), nullable=False, index=True),
        sa.Column("last_completed_date", sa.DateTime(), nullable=True),
        sa.Column("assigned_to", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("standard_ids", sa.JSON(), nullable=True),
        sa.Column("reminder_days_before", sa.Integer(), server_default="7"),
        sa.Column("reminder_sent", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "compliance_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope_type", sa.String(50), nullable=False),
        sa.Column("scope_id", sa.String(36), nullable=True),
        sa.Column("scope_name", sa.String(255), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("max_score", sa.Float(), server_default="100.0"),
        sa.Column("percentage", sa.Float(), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=True),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("previous_score", sa.Float(), nullable=True),
        sa.Column("score_change", sa.Float(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "riddor_submissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id"), nullable=False, index=True),
        sa.Column("riddor_type", sa.String(100), nullable=False),
        sa.Column("hse_reference", sa.String(100), nullable=True),
        sa.Column("submission_status", sa.String(50), server_default="pending"),
        sa.Column("submission_data", sa.JSON(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("hse_response", sa.JSON(), nullable=True),
        sa.Column("hse_response_at", sa.DateTime(), nullable=True),
        sa.Column("deadline", sa.DateTime(), nullable=False),
        sa.Column("is_overdue", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("riddor_submissions")
    op.drop_table("compliance_scores")
    op.drop_table("scheduled_audits")
    op.drop_table("certificates")
    op.drop_table("gap_analyses")
    op.drop_table("regulatory_updates")
