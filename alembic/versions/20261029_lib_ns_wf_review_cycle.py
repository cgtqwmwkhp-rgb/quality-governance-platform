"""NS-WF / W6: R20 review-cycle columns + issue attribution on versions.

Revision ID: 20261029_lib_ns_wf_review_cycle
Revises: 20261028_lib_ns_func_ctr_svc
Create Date: 2026-08-09

`documents.review_cycle_months` / `review_cycle_basis` (R20)
------------------------------------------------------------
R20 blocks issue until a document states its review cycle *and* the basis for
it. Nothing on `documents` carried either fact:
`document_categories.review_cycle` is free-text guidance for a whole category,
not this document's declared cycle.

Both are nullable with no server default and no backfill, on purpose. R20 says
there is no default cycle — a cycle is justified by risk, statute or
certification expectation — so writing one for every existing row would invent
the justification the rule exists to demand. Legacy rows read as "cycle not
stated" and are refused at the new issue transition until an owner states one.

`document_versions.issued_at` / `issued_by_id`
----------------------------------------------
`published_at` / `published_by_id` already record *who approved and when* — the
approve transition writes them. The new issue transition must not overwrite
them: that would erase the approval record to store the issue, and Document
Control already refuses to let a publisher stand in for an approver. Two new
nullable columns keep the two decisions as two facts.

No existing path reads any of these columns, so nothing changes for rows that
never reach the issue transition.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261029_lib_ns_wf_review_cycle"
down_revision: Union[str, Sequence[str], None] = "20261028_lib_ns_func_ctr_svc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ADDED: tuple[tuple[str, str, sa.types.TypeEngine], ...] = (
    ("documents", "review_cycle_months", sa.SmallInteger()),
    ("documents", "review_cycle_basis", sa.Text()),
    ("document_versions", "issued_at", sa.DateTime(timezone=True)),
    ("document_versions", "issued_by_id", sa.Integer()),
)

_ISSUED_BY_FK = "fk_document_versions_issued_by_id"


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    for table in ("documents", "document_versions"):
        existing = _columns(table)
        if not existing:
            continue
        for target_table, name, column_type in _ADDED:
            if target_table == table and name not in existing:
                op.add_column(table, sa.Column(name, column_type, nullable=True))

    if "issued_by_id" in _columns("document_versions"):
        inspector = sa.inspect(op.get_bind())
        names = {fk.get("name") for fk in inspector.get_foreign_keys("document_versions")}
        if _ISSUED_BY_FK not in names:
            op.create_foreign_key(_ISSUED_BY_FK, "document_versions", "users", ["issued_by_id"], ["id"])


def downgrade() -> None:
    """Drops the declared cycle, its basis, and the issue attribution."""
    if "issued_by_id" in _columns("document_versions"):
        inspector = sa.inspect(op.get_bind())
        names = {fk.get("name") for fk in inspector.get_foreign_keys("document_versions")}
        if _ISSUED_BY_FK in names:
            op.drop_constraint(_ISSUED_BY_FK, "document_versions", type_="foreignkey")

    for table in ("document_versions", "documents"):
        existing = _columns(table)
        if not existing:
            continue
        for target_table, name, _column_type in reversed(_ADDED):
            if target_table == table and name in existing:
                op.drop_column(table, name)
