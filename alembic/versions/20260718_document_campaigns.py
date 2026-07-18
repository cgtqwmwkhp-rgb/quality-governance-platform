"""Add document campaign spine: engineer groups, campaigns, assignments.

Revision ID: 20260718_doc_campaign
Revises: 20260726_emp_user_fk
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_doc_campaign"
down_revision: Union[str, Sequence[str], None] = "20260726_emp_user_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engineer_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_engineer_groups_tenant", "engineer_groups", ["tenant_id"])
    op.create_index("ix_engineer_groups_name", "engineer_groups", ["name"])

    op.create_table(
        "engineer_group_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("added_by_id", sa.Integer(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["engineer_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_engineer_group_member"),
    )
    op.create_index("ix_egm_tenant", "engineer_group_members", ["tenant_id"])
    op.create_index("ix_egm_group", "engineer_group_members", ["group_id"])
    op.create_index("ix_egm_user", "engineer_group_members", ["user_id"])

    op.create_table(
        "document_campaigns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("quiz_draft_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("due_within_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("require_quiz", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("require_sign", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("reminder_offsets_hours", sa.JSON(), nullable=False),
        sa.Column("audience_all_users", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("audience_department", sa.String(100), nullable=True),
        sa.Column("audience_role", sa.String(100), nullable=True),
        sa.Column("audience_group_ids", sa.JSON(), nullable=True),
        sa.Column("audience_user_ids", sa.JSON(), nullable=True),
        sa.Column("quiz_questions", sa.JSON(), nullable=True),
        sa.Column("quiz_pass_mark", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("launched_by_id", sa.Integer(), nullable=True),
        sa.Column("launched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["quiz_draft_id"], ["document_quiz_drafts.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["launched_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_campaigns_tenant", "document_campaigns", ["tenant_id"])
    op.create_index("ix_document_campaigns_document", "document_campaigns", ["document_id"])
    op.create_index("ix_document_campaigns_quiz_draft", "document_campaigns", ["quiz_draft_id"])
    op.create_index("ix_document_campaigns_status", "document_campaigns", ["status"])

    op.create_table(
        "campaign_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quiz_score", sa.Integer(), nullable=True),
        sa.Column("quiz_passed", sa.Boolean(), nullable=True),
        sa.Column("quiz_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quiz_review_needed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_quiz_answers", sa.JSON(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acceptance_statement", sa.Text(), nullable=True),
        sa.Column("signature_data", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("reminders_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["document_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "user_id", name="uq_campaign_assignment_user"),
    )
    op.create_index("ix_campaign_assignments_tenant", "campaign_assignments", ["tenant_id"])
    op.create_index("ix_campaign_assignments_campaign", "campaign_assignments", ["campaign_id"])
    op.create_index("ix_campaign_assignments_user", "campaign_assignments", ["user_id"])
    op.create_index("ix_campaign_assignments_status", "campaign_assignments", ["status"])
    op.create_index("ix_campaign_assignments_due_at", "campaign_assignments", ["due_at"])


def downgrade() -> None:
    op.drop_index("ix_campaign_assignments_due_at", table_name="campaign_assignments")
    op.drop_index("ix_campaign_assignments_status", table_name="campaign_assignments")
    op.drop_index("ix_campaign_assignments_user", table_name="campaign_assignments")
    op.drop_index("ix_campaign_assignments_campaign", table_name="campaign_assignments")
    op.drop_index("ix_campaign_assignments_tenant", table_name="campaign_assignments")
    op.drop_table("campaign_assignments")

    op.drop_index("ix_document_campaigns_status", table_name="document_campaigns")
    op.drop_index("ix_document_campaigns_quiz_draft", table_name="document_campaigns")
    op.drop_index("ix_document_campaigns_document", table_name="document_campaigns")
    op.drop_index("ix_document_campaigns_tenant", table_name="document_campaigns")
    op.drop_table("document_campaigns")

    op.drop_index("ix_egm_user", table_name="engineer_group_members")
    op.drop_index("ix_egm_group", table_name="engineer_group_members")
    op.drop_index("ix_egm_tenant", table_name="engineer_group_members")
    op.drop_table("engineer_group_members")

    op.drop_index("ix_engineer_groups_name", table_name="engineer_groups")
    op.drop_index("ix_engineer_groups_tenant", table_name="engineer_groups")
    op.drop_table("engineer_groups")
