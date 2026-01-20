"""Tier 2: AI Copilot and Digital Signatures

Revision ID: 20260120_tier2
Revises: 20260120_tier1
Create Date: 2026-01-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260120_tier2"
down_revision = "20260120_tier1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # AI Copilot Tables
    # ==========================================================================
    
    # Copilot Sessions
    op.create_table(
        "copilot_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("context_type", sa.String(100), nullable=True),
        sa.Column("context_id", sa.String(100), nullable=True),
        sa.Column("context_data", sa.JSON(), nullable=True, default={}),
        sa.Column("current_page", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_copilot_sessions_id", "copilot_sessions", ["id"])
    op.create_index("ix_copilot_sessions_user", "copilot_sessions", ["user_id", "is_active"])
    
    # Copilot Messages
    op.create_table(
        "copilot_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False, default="text"),
        sa.Column("action_type", sa.String(100), nullable=True),
        sa.Column("action_data", sa.JSON(), nullable=True),
        sa.Column("action_result", sa.JSON(), nullable=True),
        sa.Column("action_status", sa.String(20), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("feedback_rating", sa.Integer(), nullable=True),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["copilot_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_copilot_messages_id", "copilot_messages", ["id"])
    op.create_index("ix_copilot_msg_session", "copilot_messages", ["session_id", "created_at"])
    
    # Copilot Actions
    op.create_table(
        "copilot_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("parameters_schema", sa.JSON(), nullable=True, default={}),
        sa.Column("examples", sa.JSON(), nullable=True, default=[]),
        sa.Column("required_permissions", sa.JSON(), nullable=True, default=[]),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_copilot_actions_id", "copilot_actions", ["id"])
    
    # Copilot Knowledge Base
    op.create_table(
        "copilot_knowledge",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True, default=[]),
        sa.Column("source_type", sa.String(100), nullable=True),
        sa.Column("source_id", sa.String(100), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_copilot_knowledge_id", "copilot_knowledge", ["id"])
    
    # Copilot Feedback
    op.create_table(
        "copilot_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("feedback_type", sa.String(50), nullable=False),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column("user_query", sa.Text(), nullable=False),
        sa.Column("assistant_response", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["copilot_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_copilot_feedback_id", "copilot_feedback", ["id"])
    
    # ==========================================================================
    # Digital Signature Tables
    # ==========================================================================
    
    # Signature Requests
    op.create_table(
        "signature_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("reference_number", sa.String(50), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("document_content", sa.LargeBinary(), nullable=True),
        sa.Column("document_filename", sa.String(255), nullable=True),
        sa.Column("document_mime_type", sa.String(100), nullable=True),
        sa.Column("document_hash", sa.String(64), nullable=True),
        sa.Column("workflow_type", sa.String(20), nullable=False, default="sequential"),
        sa.Column("require_all", sa.Boolean(), nullable=False, default=True),
        sa.Column("status", sa.String(20), nullable=False, default="draft"),
        sa.Column("initiated_by_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("reminder_frequency", sa.Integer(), nullable=True),
        sa.Column("last_reminder_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("signed_document", sa.LargeBinary(), nullable=True),
        sa.Column("signed_document_hash", sa.String(64), nullable=True),
        sa.Column("certificate_id", sa.String(100), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True, default={}),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["initiated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signature_requests_id", "signature_requests", ["id"])
    op.create_index("ix_sig_request_status", "signature_requests", ["status", "created_at"])
    
    # Signature Request Signers
    op.create_table(
        "signature_request_signers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("signer_role", sa.String(50), nullable=False, default="signer"),
        sa.Column("order", sa.Integer(), nullable=False, default=1),
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("access_token", sa.String(255), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("first_viewed_at", sa.DateTime(), nullable=True),
        sa.Column("last_viewed_at", sa.DateTime(), nullable=True),
        sa.Column("signed_at", sa.DateTime(), nullable=True),
        sa.Column("signature_type", sa.String(20), nullable=True),
        sa.Column("signature_data", sa.Text(), nullable=True),
        sa.Column("declined_at", sa.DateTime(), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("geo_location", sa.String(255), nullable=True),
        sa.Column("auth_method", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["signature_requests.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signature_request_signers_id", "signature_request_signers", ["id"])
    op.create_index("ix_signer_request", "signature_request_signers", ["request_id", "order"])
    
    # Signatures
    op.create_table(
        "signatures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("signer_id", sa.Integer(), nullable=True),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("document_id", sa.String(100), nullable=False),
        sa.Column("document_hash", sa.String(64), nullable=False),
        sa.Column("signer_user_id", sa.Integer(), nullable=True),
        sa.Column("signer_name", sa.String(255), nullable=False),
        sa.Column("signer_email", sa.String(255), nullable=False),
        sa.Column("signer_title", sa.String(255), nullable=True),
        sa.Column("signature_type", sa.String(20), nullable=False),
        sa.Column("signature_image", sa.Text(), nullable=True),
        sa.Column("signature_text", sa.String(255), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("position_x", sa.Float(), nullable=True),
        sa.Column("position_y", sa.Float(), nullable=True),
        sa.Column("width", sa.Float(), nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column("legal_statement", sa.Text(), nullable=False),
        sa.Column("consent_given", sa.Boolean(), nullable=False, default=True),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("user_agent", sa.String(500), nullable=False),
        sa.Column("geo_location", sa.String(255), nullable=True),
        sa.Column("auth_method", sa.String(50), nullable=False),
        sa.Column("auth_timestamp", sa.DateTime(), nullable=False),
        sa.Column("certificate_serial", sa.String(100), nullable=True),
        sa.Column("certificate_issuer", sa.String(255), nullable=True),
        sa.Column("signature_hash", sa.String(64), nullable=False),
        sa.Column("signed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["signature_requests.id"]),
        sa.ForeignKeyConstraint(["signer_id"], ["signature_request_signers.id"]),
        sa.ForeignKeyConstraint(["signer_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signatures_id", "signatures", ["id"])
    
    # Signature Templates
    op.create_table(
        "signature_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("document_template", sa.LargeBinary(), nullable=True),
        sa.Column("document_filename", sa.String(255), nullable=True),
        sa.Column("signer_roles", sa.JSON(), nullable=True, default=[]),
        sa.Column("signature_fields", sa.JSON(), nullable=True, default=[]),
        sa.Column("workflow_type", sa.String(20), nullable=False, default="sequential"),
        sa.Column("expiry_days", sa.Integer(), nullable=False, default=30),
        sa.Column("reminder_days", sa.Integer(), nullable=False, default=3),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signature_templates_id", "signature_templates", ["id"])
    
    # Signature Audit Logs
    op.create_table(
        "signature_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True, default={}),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["signature_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signature_audit_logs_id", "signature_audit_logs", ["id"])
    op.create_index("ix_sig_audit_request", "signature_audit_logs", ["request_id", "created_at"])


def downgrade() -> None:
    # Drop Signature tables
    op.drop_table("signature_audit_logs")
    op.drop_table("signature_templates")
    op.drop_table("signatures")
    op.drop_table("signature_request_signers")
    op.drop_table("signature_requests")
    
    # Drop Copilot tables
    op.drop_table("copilot_feedback")
    op.drop_table("copilot_knowledge")
    op.drop_table("copilot_actions")
    op.drop_table("copilot_messages")
    op.drop_table("copilot_sessions")
