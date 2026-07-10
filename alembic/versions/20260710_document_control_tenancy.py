"""Harden document-control tenant columns and backfill child rows.

Revision ID: 20260710_doc_ctl_tenant
Revises: pm_import_sync_01
Create Date: 2026-07-10

The 20260308 tenant migration attempted to add these columns across the whole
schema. This focused migration is intentionally idempotent so databases that
missed a table during that broad migration are repaired without breaking
databases where the columns and indexes already exist.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_doc_ctl_tenant"
down_revision: Union[str, None] = "pm_import_sync_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    "controlled_documents",
    "controlled_document_versions",
    "document_approval_workflows",
    "document_approval_instances",
    "document_approval_actions",
    "document_distributions",
    "document_training_links",
    "document_access_logs",
    "obsolete_document_records",
)

DOCUMENT_CHILDREN = (
    "controlled_document_versions",
    "document_approval_instances",
    "document_distributions",
    "document_training_links",
    "document_access_logs",
    "obsolete_document_records",
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in _inspector().get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in _inspector().get_indexes(table_name)}


def _backfill_from_parent(child_table: str, parent_table: str, parent_key: str) -> None:
    op.execute(
        sa.text(
            f"""
            UPDATE {child_table}
            SET tenant_id = (
                SELECT parent.tenant_id
                FROM {parent_table} AS parent
                WHERE parent.id = {child_table}.{parent_key}
            )
            WHERE tenant_id IS NULL
              AND EXISTS (
                SELECT 1
                FROM {parent_table} AS parent
                WHERE parent.id = {child_table}.{parent_key}
                  AND parent.tenant_id IS NOT NULL
              )
            """
        )
    )


def upgrade() -> None:
    for table_name in TABLES:
        if not _table_exists(table_name):
            continue
        if not _has_column(table_name, "tenant_id"):
            op.add_column(table_name, sa.Column("tenant_id", sa.Integer(), nullable=True))
        index_name = f"ix_{table_name}_tenant_id"
        if not _has_index(table_name, index_name):
            op.create_index(index_name, table_name, ["tenant_id"])

    if _table_exists("controlled_documents"):
        for child_table in DOCUMENT_CHILDREN:
            if _table_exists(child_table):
                _backfill_from_parent(child_table, "controlled_documents", "document_id")

    if _table_exists("document_approval_actions") and _table_exists("document_approval_instances"):
        _backfill_from_parent(
            "document_approval_actions",
            "document_approval_instances",
            "instance_id",
        )


def downgrade() -> None:
    # Data attribution cannot be safely reversed. The nullable columns also
    # pre-date this repair migration on canonical installations, so removing
    # them here would destroy schema owned by 20260308_tenant.
    pass
