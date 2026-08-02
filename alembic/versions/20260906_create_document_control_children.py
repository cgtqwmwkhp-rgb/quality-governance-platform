"""Create the seven document-control child tables (C-24).

Revision ID: 20260906_doc_ctl_children
Revises: 20260905_doc_chunk_fts
Create Date: 2026-09-06

``src/domain/models/document_control.py`` declares nine tables. Two of them
(``controlled_documents``, ``controlled_document_versions``) were given a create
migration on 2026-07-11; the other seven never had one, so they are absent from
every Alembic-built deployment and were confirmed absent in production by the
Run 021 measurement. ``docs/ops/absent-table-disclosure.md`` records which
surfaces sit above them and what those surfaces answer while they are missing.

This closes the whole Documents cluster of the deferral register in one
migration, so all seven names come off ``_ALEMBIC_CHECK_EXCLUDED_TABLES`` in the
same PR.

Shape is taken from ``alembic.autogenerate`` against a database at the previous
head, so ``alembic check`` produces no operation for any of these tables once
they stop being excluded.

Additive and idempotent. Each table is skipped if it already exists, because
this migration runs on installations nobody has enumerated and a create is the
one operation that cannot be made safe by ordering alone.

Ordering note: ``20260710_doc_ctl_tenant`` and the two 20260711 ``tenant_id``
NOT NULL migrations already ran by this point and skipped every one of these
tables, having found nothing to alter. The columns they would have produced are
therefore written here directly -- ``tenant_id`` is ``NOT NULL`` on
``document_access_logs`` and ``obsolete_document_records`` and nullable on the
other five, which is what the models declare.

Not in scope: row-level security. The three document tables under FORCE RLS were
added by a dedicated expand migration plus a matching entry in
``RLS_TABLES`` (``src/infrastructure/middleware/tenant_context.py``), and
``tests/integration/test_run026_rls_least_privilege_postgres.py`` fails on any
policy that is not registered there. Expanding RLS onto these tables is a
separate, registered decision; creating them here does not pre-empt it.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_doc_ctl_children"
down_revision: Union[str, Sequence[str], None] = "20260905_doc_chunk_fts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Drop order is the reverse of create order, so foreign keys never dangle.
TABLES_IN_DEPENDENCY_ORDER = (
    "document_approval_workflows",
    "document_approval_instances",
    "document_approval_actions",
    "document_distributions",
    "document_training_links",
    "document_access_logs",
    "obsolete_document_records",
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _create_document_approval_workflows() -> None:
    op.create_table(
        "document_approval_workflows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("applicable_document_types", sa.JSON(), nullable=False),
        sa.Column("applicable_categories", sa.JSON(), nullable=True),
        sa.Column("applicable_departments", sa.JSON(), nullable=True),
        sa.Column("workflow_steps", sa.JSON(), nullable=False),
        sa.Column("allow_parallel_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("require_all_approvals", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_escalate_after_days", sa.Integer(), nullable=True),
        sa.Column("notify_on_approval", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notify_on_rejection", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_approval_workflows_tenant_id",
        "document_approval_workflows",
        ["tenant_id"],
    )


def _create_document_approval_instances() -> None:
    op.create_table(
        "document_approval_instances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("initiated_by", sa.Integer(), nullable=True),
        sa.Column("initiated_date", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_date", sa.DateTime(), nullable=True),
        sa.Column("final_decision", sa.String(length=50), nullable=True),
        sa.Column("final_comments", sa.Text(), nullable=True),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("is_overdue", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_id"], ["controlled_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["initiated_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["controlled_document_versions.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["document_approval_workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_approval_instances_tenant_id",
        "document_approval_instances",
        ["tenant_id"],
    )


def _create_document_approval_actions() -> None:
    op.create_table(
        "document_approval_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("workflow_step", sa.Integer(), nullable=False),
        sa.Column("approver_id", sa.Integer(), nullable=False),
        sa.Column("approver_name", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("conditions", sa.Text(), nullable=True),
        sa.Column("delegated_to", sa.Integer(), nullable=True),
        sa.Column("delegation_reason", sa.Text(), nullable=True),
        sa.Column("action_date", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["delegated_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["instance_id"], ["document_approval_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_approval_actions_tenant_id",
        "document_approval_actions",
        ["tenant_id"],
    )


def _create_document_distributions() -> None:
    op.create_table(
        "document_distributions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("recipient_type", sa.String(length=50), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=True),
        sa.Column("recipient_name", sa.String(length=255), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("distribution_type", sa.String(length=50), nullable=False, server_default="controlled"),
        sa.Column("copy_number", sa.String(length=50), nullable=True),
        sa.Column("is_holder_of_record", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notified_date", sa.DateTime(), nullable=True),
        sa.Column("notification_method", sa.String(length=50), nullable=False, server_default="email"),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("acknowledged_date", sa.DateTime(), nullable=True),
        sa.Column("acknowledgment_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_accessed", sa.DateTime(), nullable=True),
        sa.Column("is_recalled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("recalled_date", sa.DateTime(), nullable=True),
        sa.Column("return_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("return_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_id"], ["controlled_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["controlled_document_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_distributions_tenant_id",
        "document_distributions",
        ["tenant_id"],
    )


def _create_document_training_links() -> None:
    op.create_table(
        "document_training_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("training_title", sa.String(length=255), nullable=False),
        sa.Column("training_description", sa.Text(), nullable=True),
        sa.Column("training_type", sa.String(length=50), nullable=False, server_default="awareness"),
        sa.Column("target_roles", sa.JSON(), nullable=True),
        sa.Column("target_departments", sa.JSON(), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("completion_deadline_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("retraining_frequency_months", sa.Integer(), nullable=True),
        sa.Column("trigger_on_new_version", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("trigger_on_new_distribution", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_id"], ["controlled_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_training_links_tenant_id",
        "document_training_links",
        ["tenant_id"],
    )


def _create_document_access_logs() -> None:
    op.create_table(
        "document_access_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("user_name", sa.String(length=255), nullable=False),
        sa.Column("user_email", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("action_details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("session_id", sa.String(length=100), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_id"], ["controlled_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["controlled_document_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_access_logs_document_id", "document_access_logs", ["document_id"])
    op.create_index("ix_document_access_logs_tenant_id", "document_access_logs", ["tenant_id"])
    op.create_index("ix_document_access_logs_timestamp", "document_access_logs", ["timestamp"])


def _create_obsolete_document_records() -> None:
    op.create_table(
        "obsolete_document_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("obsolete_date", sa.DateTime(), nullable=False),
        sa.Column("obsolete_reason", sa.Text(), nullable=False),
        sa.Column("obsoleted_by_id", sa.Integer(), nullable=True),
        sa.Column("obsoleted_by_name", sa.String(length=255), nullable=True),
        sa.Column("superseded_by_id", sa.Integer(), nullable=True),
        sa.Column("superseded_by_number", sa.String(length=50), nullable=True),
        sa.Column("watermark_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("physical_copies_recalled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("recall_date", sa.DateTime(), nullable=True),
        sa.Column("retention_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("retention_end_date", sa.DateTime(), nullable=True),
        sa.Column("disposal_date", sa.DateTime(), nullable=True),
        sa.Column("disposal_method", sa.String(length=100), nullable=True),
        sa.Column("disposal_confirmed_by", sa.String(length=255), nullable=True),
        sa.Column("archive_location", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_id"], ["controlled_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["obsoleted_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["controlled_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_obsolete_document_records_tenant_id",
        "obsolete_document_records",
        ["tenant_id"],
    )


_CREATORS = {
    "document_approval_workflows": _create_document_approval_workflows,
    "document_approval_instances": _create_document_approval_instances,
    "document_approval_actions": _create_document_approval_actions,
    "document_distributions": _create_document_distributions,
    "document_training_links": _create_document_training_links,
    "document_access_logs": _create_document_access_logs,
    "obsolete_document_records": _create_obsolete_document_records,
}


def upgrade() -> None:
    for table_name in TABLES_IN_DEPENDENCY_ORDER:
        if _table_exists(table_name):
            continue
        _CREATORS[table_name]()


def downgrade() -> None:
    for table_name in reversed(TABLES_IN_DEPENDENCY_ORDER):
        if _table_exists(table_name):
            op.drop_table(table_name)
