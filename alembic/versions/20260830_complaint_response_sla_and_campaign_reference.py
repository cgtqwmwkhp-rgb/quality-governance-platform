"""Complaint response-SLA columns and a stored document-campaign reference.

Revision ID: 20260830_sla_cam_ref
Revises: 20260829_inv_tenant_src
Create Date: 2026-08-30

PX-210 — complaints carried no response deadline at all, so the detail page could
only state that none was stored. Three nullable columns give the module somewhere
honest to keep one: ``response_sla_hours`` (the agreed target), ``response_due_at``
(derived from ``received_date`` unless a caller sets it explicitly) and
``first_response_at`` (when the complainant was actually answered). They stay
nullable on purpose — a complaint with no agreed SLA must keep reading as "none
stored" rather than silently acquiring a deadline nobody agreed to.

PX-222 — ``CAM-YYYY-NNNN`` was assembled in the browser from the surrogate id, so
two surfaces could disagree (the campaign panel used launched_at ?? created_at, the
compliance table used launched_at alone and fell back to the *current* year for a
draft). ``document_campaigns.reference_number`` makes the reference a stored fact.

The backfill reproduces exactly what the campaign panel renders today —
``CAM-<year of launched_at, else created_at>-<zero-padded id>`` — so no campaign
reference visibly changes on deploy. That expression is unique by construction:
the id is a global primary key, so no two rows can produce the same pair.

The column is nullable rather than NOT NULL because the previous release is still
inserting campaigns during a rolling deploy and must not start failing; every write
path in this release mints a reference through ReferenceNumberService.

Revision id kept <= 32 chars for alembic_version.version_num VARCHAR(32).
"""

from __future__ import annotations

from datetime import timezone
from typing import Optional, Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_sla_cam_ref"
down_revision: Union[str, Sequence[str], None] = "20260829_inv_tenant_src"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CAMPAIGN_REF_INDEX = "ix_document_campaigns_reference_number"

_campaigns = sa.table(
    "document_campaigns",
    sa.column("id", sa.Integer),
    sa.column("reference_number", sa.String),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("launched_at", sa.DateTime(timezone=True)),
)


def _utc_year(value) -> Optional[int]:
    """Year of a stored timestamp, reading naive values as the UTC they are.

    SQLite hands back naive datetimes for ``DateTime(timezone=True)``; calling
    ``astimezone`` on those would reinterpret them in the server's local zone and
    shift a New Year's Eve campaign into the wrong year.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.year
    return value.astimezone(timezone.utc).year


def _campaign_reference(campaign_id: int, year: int) -> str:
    return f"CAM-{year}-{campaign_id:04d}"


def _backfill_campaign_references() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(_campaigns.c.id, _campaigns.c.created_at, _campaigns.c.launched_at)
        .where(_campaigns.c.reference_number.is_(None))
        .order_by(_campaigns.c.id)
    ).fetchall()

    for row in rows:
        year = _utc_year(row.launched_at) or _utc_year(row.created_at)
        if year is None:
            # created_at is NOT NULL, so this is unreachable in practice. Leave the
            # row unset rather than invent a year: the API reports a missing
            # reference honestly instead of minting a wrong one.
            continue
        bind.execute(
            _campaigns.update()
            .where(_campaigns.c.id == row.id)
            .values(reference_number=_campaign_reference(row.id, year))
        )


def upgrade() -> None:
    op.add_column("complaints", sa.Column("response_sla_hours", sa.Integer(), nullable=True))
    op.add_column("complaints", sa.Column("response_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("complaints", sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("document_campaigns", sa.Column("reference_number", sa.String(length=20), nullable=True))
    _backfill_campaign_references()
    op.create_index(
        op.f(CAMPAIGN_REF_INDEX),
        "document_campaigns",
        ["reference_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f(CAMPAIGN_REF_INDEX), table_name="document_campaigns")
    op.drop_column("document_campaigns", "reference_number")

    op.drop_column("complaints", "first_response_at")
    op.drop_column("complaints", "response_due_at")
    op.drop_column("complaints", "response_sla_hours")
