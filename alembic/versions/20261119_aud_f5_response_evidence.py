"""AUD-F5 — a real join between an audit answer and its evidence.

Revision ID: 20261119_aud_f5_resp_evid
Revises: 20260901_comp_cov

The parent is **not** the numerically-latest filename in this directory.
``20261118_engineer_roster_archived_at`` looks like the tip and is not: the
CB-PR competence-board revisions were filed as ``20260901_*`` while chaining
*after* it (``20261118_eng_roster_arch`` → ``20260901_pams_comp`` →
``comp_cr`` → ``comp_bind`` → ``comp_cov``). Revising the file that sorts last
would therefore have forked the chain, and a second head makes
``alembic upgrade head`` refuse on deploy rather than at review.
``test_the_new_revision_is_the_only_head`` computes this instead of trusting the
filenames.

ADD TABLE only. No column is altered, no row is rewritten, nothing is locked
beyond the moment ``CREATE TABLE`` takes, so this is safe to run against a live
database while field audits are in progress.

**No backfill, deliberately.** The historical orphans this slice exists because
of (AUD-2026-0087) can only be reconstructed by reading
``audit_responses.response_json.evidence_asset_ids`` for every response in the
database and by parsing ``evidence_assets.description`` for the
``audit_question:{id}`` tag that AUD-PHOTO-02 writes. That is a full scan of
both tables plus a write per matched pair, and the write would have to hold
those rows while the field client is saving into them — the kill condition
recorded for this slice was exactly "join backfill needs downtime". So it is
not attempted here: for every response written before this revision,
``response_json.evidence_asset_ids`` remains the read projection, and
AUD-F4's completion gate keeps resolving those ids against the live
``evidence_assets`` rows for the run rather than against this table. A backfill
is a separate, restartable, batched job if it is ever wanted; it is not a
migration.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261119_aud_f5_resp_evid"
down_revision: Union[str, Sequence[str], None] = "20260901_comp_cov"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "audit_response_evidence"

# Kept in step with ``AuditEvidenceRole`` in
# src/domain/models/audit_response_evidence.py; the model asserts the pair match.
ROLE_CHECK = "role IN ('photo', 'signature', 'attachment')"


def _table_exists() -> bool:
    return sa.inspect(op.get_bind()).has_table(TABLE)


def upgrade() -> None:
    if _table_exists():
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("response_id", sa.Integer(), nullable=False),
        sa.Column("evidence_asset_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), server_default=sa.text("'photo'"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # ON DELETE CASCADE: a link cannot outlive the answer it describes.
        sa.ForeignKeyConstraint(["response_id"], ["audit_responses.id"], ondelete="CASCADE"),
        # No ondelete: a physical delete of cited evidence is refused rather than
        # silently unlinking it. Evidence is soft-deleted in normal operation.
        sa.ForeignKeyConstraint(["evidence_asset_id"], ["evidence_assets.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "response_id",
            "evidence_asset_id",
            name="uq_audit_response_evidence_response_asset",
        ),
        sa.CheckConstraint(ROLE_CHECK, name="ck_audit_response_evidence_role"),
    )
    op.create_index("ix_audit_response_evidence_response_id", TABLE, ["response_id"])
    op.create_index("ix_audit_response_evidence_evidence_asset_id", TABLE, ["evidence_asset_id"])
    op.create_index("ix_audit_response_evidence_created_at", TABLE, ["created_at"])


def downgrade() -> None:
    if _table_exists():
        op.drop_table(TABLE)
