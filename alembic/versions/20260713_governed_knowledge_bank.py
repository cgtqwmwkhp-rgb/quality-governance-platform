"""Add governed knowledge bank tables and compliance evidence AI-first columns.

Revision ID: 20260713_governed_kb
Revises: 20260713_nm_tenant_nn
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_governed_kb"
down_revision: Union[str, Sequence[str], None] = "20260713_nm_tenant_nn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "compliance_evidence_links",
        sa.Column("status", sa.String(20), nullable=True, server_default="proposed"),
    )
    op.add_column(
        "compliance_evidence_links",
        sa.Column("scheme", sa.String(50), nullable=True),
    )
    op.add_column(
        "compliance_evidence_links",
        sa.Column("auto_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "compliance_evidence_links",
        sa.Column("rationale", sa.Text(), nullable=True),
    )
    op.create_index("ix_cel_status", "compliance_evidence_links", ["status"])

    op.create_table(
        "document_discussion_threads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
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
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ddt_tenant", "document_discussion_threads", ["tenant_id"])
    op.create_index("ix_ddt_document", "document_discussion_threads", ["document_id"])

    op.create_table(
        "document_discussion_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_ai_draft", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["document_discussion_threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ddm_tenant", "document_discussion_messages", ["tenant_id"])
    op.create_index("ix_ddm_thread", "document_discussion_messages", ["thread_id"])

    op.create_table(
        "document_quiz_drafts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("pass_mark", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
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
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dqd_tenant", "document_quiz_drafts", ["tenant_id"])
    op.create_index("ix_dqd_document", "document_quiz_drafts", ["document_id"])

    op.create_table(
        "regulatory_watch_impacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("update_id", sa.String(100), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
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
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rwi_tenant", "regulatory_watch_impacts", ["tenant_id"])
    op.create_index("ix_rwi_update", "regulatory_watch_impacts", ["update_id"])

    op.create_table(
        "ai_decision_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("auto_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("payload", sa.JSON(), nullable=True),
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
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_adl_tenant", "ai_decision_logs", ["tenant_id"])
    op.create_index("ix_adl_action", "ai_decision_logs", ["action"])


def downgrade() -> None:
    op.drop_index("ix_adl_action", table_name="ai_decision_logs")
    op.drop_index("ix_adl_tenant", table_name="ai_decision_logs")
    op.drop_table("ai_decision_logs")

    op.drop_index("ix_rwi_update", table_name="regulatory_watch_impacts")
    op.drop_index("ix_rwi_tenant", table_name="regulatory_watch_impacts")
    op.drop_table("regulatory_watch_impacts")

    op.drop_index("ix_dqd_document", table_name="document_quiz_drafts")
    op.drop_index("ix_dqd_tenant", table_name="document_quiz_drafts")
    op.drop_table("document_quiz_drafts")

    op.drop_index("ix_ddm_thread", table_name="document_discussion_messages")
    op.drop_index("ix_ddm_tenant", table_name="document_discussion_messages")
    op.drop_table("document_discussion_messages")

    op.drop_index("ix_ddt_document", table_name="document_discussion_threads")
    op.drop_index("ix_ddt_tenant", table_name="document_discussion_threads")
    op.drop_table("document_discussion_threads")

    op.drop_index("ix_cel_status", table_name="compliance_evidence_links")
    op.drop_column("compliance_evidence_links", "rationale")
    op.drop_column("compliance_evidence_links", "auto_applied")
    op.drop_column("compliance_evidence_links", "scheme")
    op.drop_column("compliance_evidence_links", "status")
