"""Add missing FK indexes for documents and investigations.

Revision ID: 20260306_doc_inv_idx
Revises: 20260306_risk_idx
Create Date: 2026-03-06
"""

from typing import Union

from alembic import op

revision: str = "20260306_doc_inv_idx"
down_revision: Union[str, None] = "20260306_rc_idx"
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_documents_linked_policy_id", "documents", ["linked_policy_id"]),
    ("ix_documents_linked_standard_id", "documents", ["linked_standard_id"]),
    ("ix_documents_created_by_id", "documents", ["created_by_id"]),
    ("ix_document_annotations_document_id", "document_annotations", ["document_id"]),
    ("ix_document_annotations_user_id", "document_annotations", ["user_id"]),
    ("ix_document_versions_document_id", "document_versions", ["document_id"]),
    ("ix_investigation_comments_parent_comment_id", "investigation_comments", ["parent_comment_id"]),
    ("ix_investigation_revision_events_actor_id", "investigation_revision_events", ["actor_id"]),
]


def upgrade() -> None:
    for idx_name, table, columns in INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({', '.join(columns)})")


def downgrade() -> None:
    for idx_name, _, _ in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {idx_name}")
