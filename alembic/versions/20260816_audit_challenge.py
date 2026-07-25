"""Audit Builder Check & Challenge coach sessions.

Revision ID: 20260816_audit_challenge
Revises: 20260815_safety_insights
Create Date: 2026-08-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_audit_challenge"
down_revision: Union[str, Sequence[str], None] = "20260815_safety_insights"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_challenge_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("audit_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_message", sa.String(255), nullable=True),
        sa.Column("chip_id", sa.String(80), nullable=True),
        sa.Column("user_message", sa.Text(), nullable=True),
        sa.Column("brief_json", sa.JSON(), nullable=True),
        sa.Column("template_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("models_used_json", sa.JSON(), nullable=True),
        sa.Column("grounding_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_audit_challenge_sessions_tenant_id", "audit_challenge_sessions", ["tenant_id"])
    op.create_index("ix_audit_challenge_sessions_status", "audit_challenge_sessions", ["status"])
    op.create_index(
        "ix_audit_challenge_sessions_tenant_status", "audit_challenge_sessions", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_audit_challenge_sessions_tenant_created", "audit_challenge_sessions", ["tenant_id", "created_at"]
    )
    op.create_index("ix_audit_challenge_sessions_template_id", "audit_challenge_sessions", ["template_id"])

    op.create_table(
        "audit_challenge_turns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("audit_challenge_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chip_id", sa.String(80), nullable=True),
        sa.Column("citations_json", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_challenge_turns_session", "audit_challenge_turns", ["session_id"])
    op.create_index("ix_audit_challenge_turns_tenant_id", "audit_challenge_turns", ["tenant_id"])

    op.create_table(
        "audit_challenge_proposals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("audit_challenge_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "turn_id",
            sa.Integer(),
            sa.ForeignKey("audit_challenge_turns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("proposal_key", sa.String(80), nullable=False),
        sa.Column("target_path", sa.String(300), nullable=False, server_default=""),
        sa.Column("change_type", sa.String(80), nullable=False, server_default="revise_question"),
        sa.Column("dimension", sa.String(80), nullable=True),
        sa.Column("assessor_failure_mode", sa.String(500), nullable=True),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("citations_json", sa.JSON(), nullable=True),
        sa.Column("decision", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("edited_after_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_challenge_proposals_session", "audit_challenge_proposals", ["session_id"])
    op.create_index(
        "ix_audit_challenge_proposals_decision", "audit_challenge_proposals", ["session_id", "decision"]
    )
    op.create_index("ix_audit_challenge_proposals_tenant_id", "audit_challenge_proposals", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("audit_challenge_proposals")
    op.drop_table("audit_challenge_turns")
    op.drop_table("audit_challenge_sessions")
