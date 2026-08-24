"""WI-2 / L-32: file homes → documents.id

Revision ID: 20261031_lib_wi2_homes
Revises: 20261030_lib_wi1_cel
Create Date: 2026-08-09

Absolute rules (F-3 / F-7 / L-32)
---------------------------------
- Register ``documents.id`` is the only library file home. This revision adds a
  *link* from the occurrence tables to it; it does not create a second blob SoT
  and does not move any file.
- ``ON DELETE SET NULL``: deleting a Register document must not delete a Planet
  Mark evidence row or a case evidence asset. The occurrence row owns its own
  metadata and keeps it; only the Library link goes.
- Nullable, with no backfill. A link is a claim that this occurrence *is* that
  Register document, and nothing in the database proves that claim for legacy
  rows. Guessing one from a filename would file coverage nobody attested to, so
  legacy rows stay NULL until a steward promotes them or a content match is
  proven (``src/domain/services/library_file_home_link.py``).

Why ``uvdb_audit_response.documents_presented`` gets no DDL here
---------------------------------------------------------------
The presented list converges on ``{"document_id": int|null, "label": str|null}``
elements, which is a JSON *projection* rather than a column, so there is nothing
to alter. It is normalised on write by the application layer, where the caller's
tenant is known and an unresolvable title can honestly stay
``{"document_id": null, "label": "<original>"}``. A data migration would have to
guess those ids from free text with no tenant context, which is the one thing
L-32 forbids.

Out of scope (do not add here)
------------------------------
- ``compliance_evidence`` soft-delete / ``cover_kind``, ``standards.kind``,
  ``clauses.catalogue_key`` — WI-1 (``20261030_lib_wi1_cel``).
- Dropping ``carbon_evidence.storage_key`` / ``evidence_assets.storage_key`` and
  shrinking the F-3 allowlist — later cut, once every live row carries a link.
- ``collaborative_*`` drop (WJ-0), DocumentDetail body.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261031_lib_wi2_homes"
down_revision: Union[str, Sequence[str], None] = "20261030_lib_wi1_cel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

#: table → (foreign key name, index name). Applied in order on upgrade and in
#: reverse on downgrade.
LINKED_HOMES: tuple[tuple[str, str, str], ...] = (
    ("carbon_evidence", "fk_carbon_evidence_document_id", "ix_carbon_evidence_document_id"),
    ("evidence_assets", "fk_evidence_assets_document_id", "ix_evidence_assets_document_id"),
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {c["name"] for c in _inspector().get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {i["name"] for i in _inspector().get_indexes(table_name) if i.get("name")}


def _fk_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {fk["name"] for fk in _inspector().get_foreign_keys(table_name) if fk.get("name")}


def _supports_add_constraint() -> bool:
    """SQLite cannot ``ALTER TABLE ... ADD CONSTRAINT`` outside batch mode.

    Migrations run on PostgreSQL everywhere that matters; this keeps the column
    and its index landing on SQLite instead of aborting the whole revision.
    """
    return op.get_bind().dialect.name != "sqlite"


def _add_document_id(table_name: str, *, fk_name: str, index_name: str) -> None:
    if not _table_exists(table_name):
        logger.info("%s: %s absent, skipping document_id link", revision, table_name)
        return
    if "document_id" not in _columns(table_name):
        op.add_column(table_name, sa.Column("document_id", sa.Integer(), nullable=True))
    if fk_name not in _fk_names(table_name):
        if _supports_add_constraint():
            op.create_foreign_key(
                fk_name,
                table_name,
                "documents",
                ["document_id"],
                ["id"],
                ondelete="SET NULL",
            )
        else:
            logger.info("%s: %s cannot add %s, dialect has no ADD CONSTRAINT", revision, table_name, fk_name)
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, ["document_id"])


def upgrade() -> None:
    for table_name, fk_name, index_name in LINKED_HOMES:
        _add_document_id(table_name, fk_name=fk_name, index_name=index_name)


def downgrade() -> None:
    """Strip the optional Register links. No occurrence row or blob is lost."""
    for table_name, fk_name, index_name in reversed(LINKED_HOMES):
        if not _table_exists(table_name):
            continue
        if index_name in _index_names(table_name):
            op.drop_index(index_name, table_name=table_name)
        if fk_name in _fk_names(table_name):
            op.drop_constraint(fk_name, table_name=table_name, type_="foreignkey")
        if "document_id" in _columns(table_name):
            op.drop_column(table_name, "document_id")
