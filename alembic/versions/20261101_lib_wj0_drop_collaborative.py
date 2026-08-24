"""WJ-0 / L-35a: drop the dormant collaborative CRDT stack

Revision ID: 20261101_lib_wj0_drop
Revises: 20261031_lib_wi2_homes
Create Date: 2026-08-10

What goes and why (L-35a, enhance-never-replicate)
--------------------------------------------------
``20260120_tier1_enterprise_features`` created a Yjs CRDT co-editing stack that
was never productised: no route ever read these tables, the service that wrote
them was imported by nothing, and the frontend hook that would have driven them
connects to ``/api/v1/realtime/collab/{documentId}``, a handler that has never
existed on any branch. ``yjs`` / ``y-websocket`` are in neither
``package.json`` nor ``requirements.txt``. The inventory behind that claim is
``docs/governance/library-wj0-drop-collaborative-inventory.md``.

Left standing, it is a trap: the WJ-1 native document editor would either build
on a CRDT layer nobody has ever run, or add a second document-body store beside
it. So the tables go before the editor lands, not after.

``document_comments`` and ``user_presence`` go with it
-------------------------------------------------------
Both are siblings declared in the same model module and created by the same
revision, and both are equally unwired:

- ``document_comments`` has no route, service caller or frontend consumer. The
  live commenting product need is already served by
  ``document_discussion_threads`` / ``document_discussion_messages``
  (``src/domain/models/governed_knowledge.py``), which *are* wired to
  ``/api/v1/governed-knowledge``. Keeping an unread second comment table beside
  a read one is precisely the duplicate SoT the anti-dupe plan forbids.
- ``user_presence`` is not what ``/api/v1/realtime/presence/{user_id}`` reads.
  That route answers from the in-memory ``connection_manager``; the table has
  never been written by anything in the request path.

Not touched here
----------------
``/api/v1/realtime/ws|stats|online-users|presence|broadcast`` and
``connection_manager`` stay exactly as they are: they carry notifications and
in-memory presence, neither of which is CRDT. Their keep-or-cut decision is a
separate question from this one, and no ``/collab`` handler is added.

Row counts
----------
Production row counts could not be queried when this revision was written (no
operator access to the production database from the authoring environment), so
the counts are logged at ``INFO`` immediately before each ``DROP`` rather than
asserted in advance — the deploy log records what was actually destroyed. The
drop is unconditional on purpose: any row present is abandoned CRDT state for a
feature that was never reachable, there is no migration path to the native
editor for a Yjs blob, and a migration that refuses on a non-empty table would
wedge the deploy on data nobody can act on.

Downgrade
---------
Recreates all five tables exactly as the history built them: the
``20260120_tier1_enterprise_features`` DDL plus the ``tenant_id`` column and
``ix_<table>_tenant_id`` index that ``20260308_tenant`` added. Data is *not*
recoverable — a downgrade returns the schema, not the CRDT blobs.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261101_lib_wj0_drop"
down_revision: Union[str, Sequence[str], None] = "20261031_lib_wi2_homes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

#: table → index names to drop before the table. Child tables first: both
#: ``collaborative_sessions`` and ``collaborative_changes`` carry a foreign key
#: to ``collaborative_documents``.
DROP_ORDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("collaborative_changes", ("ix_collab_change_doc", "ix_collaborative_changes_tenant_id")),
    ("collaborative_sessions", ("ix_collab_session_active", "ix_collaborative_sessions_tenant_id")),
    ("collaborative_documents", ("ix_collab_doc_entity", "ix_collaborative_documents_tenant_id")),
    ("document_comments", ("ix_document_comments_tenant_id",)),
    ("user_presence", ("ix_user_presence_tenant_id",)),
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _index_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {index["name"] for index in _inspector().get_indexes(table_name) if index.get("name")}


def _log_row_count(table_name: str) -> None:
    """Record what the drop destroys, in the deploy log, before it happens.

    The table name comes from ``DROP_ORDER``, a module-level literal, so the
    interpolation carries no external input.
    """
    count = op.get_bind().execute(sa.text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
    logger.info("%s: dropping %s holding %s row(s)", revision, table_name, count)


def upgrade() -> None:
    for table_name, index_names in DROP_ORDER:
        if not _table_exists(table_name):
            logger.info("%s: %s absent, nothing to drop", revision, table_name)
            continue
        _log_row_count(table_name)
        present = _index_names(table_name)
        for index_name in index_names:
            if index_name in present:
                op.drop_index(index_name, table_name=table_name)
        op.drop_table(table_name)


def _downgrade_collaborative_documents() -> None:
    op.create_table(
        "collaborative_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=True),
        sa.Column("yjs_state", sa.LargeBinary(), nullable=True),
        sa.Column("yjs_state_vector", sa.LargeBinary(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("last_snapshot", sa.LargeBinary(), nullable=True),
        sa.Column("last_snapshot_at", sa.DateTime(), nullable=True),
        sa.Column("is_locked", sa.Boolean(), nullable=True),
        sa.Column("locked_by_id", sa.Integer(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("lock_reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["locked_by_id"], ["users.id"]),
    )
    op.create_index("ix_collab_doc_entity", "collaborative_documents", ["entity_type", "entity_id"])
    op.create_index("ix_collaborative_documents_tenant_id", "collaborative_documents", ["tenant_id"])


def _downgrade_collaborative_sessions() -> None:
    op.create_table(
        "collaborative_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("user_name", sa.String(255), nullable=False),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("user_avatar", sa.String(500), nullable=True),
        sa.Column("user_color", sa.String(7), nullable=True),
        sa.Column("cursor_position", sa.JSON(), nullable=True),
        sa.Column("selection_range", sa.JSON(), nullable=True),
        sa.Column("current_field", sa.String(100), nullable=True),
        sa.Column("is_editing", sa.Boolean(), nullable=True),
        sa.Column("is_typing", sa.Boolean(), nullable=True),
        sa.Column("connection_id", sa.String(100), nullable=True),
        sa.Column("client_version", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("left_at", sa.DateTime(), nullable=True),
        # Appended last, not declared second as the model has it: 20260308_tenant
        # added this column with ALTER TABLE, so that is where it sits on every
        # database this revision can be asked to downgrade.
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
        sa.ForeignKeyConstraint(["document_id"], ["collaborative_documents.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_collab_session_active", "collaborative_sessions", ["is_active", "last_seen_at"])
    op.create_index("ix_collaborative_sessions_tenant_id", "collaborative_sessions", ["tenant_id"])


def _downgrade_collaborative_changes() -> None:
    op.create_table(
        "collaborative_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(50), nullable=False),
        sa.Column("change_data", sa.JSON(), nullable=False),
        sa.Column("path", sa.String(500), nullable=True),
        sa.Column("offset", sa.Integer(), nullable=True),
        sa.Column("length", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        # Appended last for the same reason as collaborative_sessions.tenant_id.
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_id"], ["collaborative_documents.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_collab_change_doc", "collaborative_changes", ["document_id", "created_at"])
    op.create_index("ix_collaborative_changes_tenant_id", "collaborative_changes", ["tenant_id"])


def _downgrade_document_comments() -> None:
    op.create_table(
        "document_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("thread_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("anchor_path", sa.String(500), nullable=True),
        sa.Column("anchor_offset", sa.Integer(), nullable=True),
        sa.Column("anchor_length", sa.Integer(), nullable=True),
        sa.Column("quoted_text", sa.Text(), nullable=True),
        sa.Column("mentions", sa.JSON(), nullable=True),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("author_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("resolved_by_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("reactions", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["document_comments.id"]),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"]),
    )
    op.create_index("ix_document_comments_tenant_id", "document_comments", ["tenant_id"])


def _downgrade_user_presence() -> None:
    op.create_table(
        "user_presence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("custom_status", sa.String(255), nullable=True),
        sa.Column("current_page", sa.String(255), nullable=True),
        sa.Column("current_entity_type", sa.String(100), nullable=True),
        sa.Column("current_entity_id", sa.String(100), nullable=True),
        sa.Column("device_type", sa.String(50), nullable=True),
        sa.Column("browser", sa.String(100), nullable=True),
        sa.Column("connection_count", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("went_away_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_user_presence_tenant_id", "user_presence", ["tenant_id"])


def downgrade() -> None:
    """Rebuild the schema the CRDT stack had. The data does not come back."""
    if not _table_exists("collaborative_documents"):
        _downgrade_collaborative_documents()
    if not _table_exists("collaborative_sessions"):
        _downgrade_collaborative_sessions()
    if not _table_exists("collaborative_changes"):
        _downgrade_collaborative_changes()
    if not _table_exists("document_comments"):
        _downgrade_document_comments()
    if not _table_exists("user_presence"):
        _downgrade_user_presence()
