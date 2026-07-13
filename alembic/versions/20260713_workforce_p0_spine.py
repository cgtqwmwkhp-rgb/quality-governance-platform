"""Workforce P0 spine: training_tickets + requirement allocate filters.

Revision ID: 20260713_wf_p0_spine
Revises: 20260713_op_assess
Create Date: 2026-07-13

Creates first-class training_tickets (scheme, number, expiry, verify_state,
evidence FK, tenant_id NOT NULL). Adds role_key/site on competency_requirements.
Best-effort backfill from engineers.certifications_json (legacy blob).
"""

from __future__ import annotations

import json
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_wf_p0_spine"
down_revision: Union[str, Sequence[str], None] = "20260713_op_assess"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in _inspector().get_columns(table_name)}


def _backfill_tickets_from_certifications_json() -> None:
    """Promote legacy certifications_json entries into training_tickets.

    Does not invent tenant_id. Engineers without tenant_id are skipped (fail-safe).
    Expected JSON shape: [{name|scheme, number|ticket_number, issuer, issued|issued_at, expiry|expires_at}]
    """
    if not _table_exists("engineers") or not _table_exists("training_tickets"):
        return
    if not _has_column("engineers", "certifications_json"):
        return

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, tenant_id, certifications_json
            FROM engineers
            WHERE certifications_json IS NOT NULL
              AND tenant_id IS NOT NULL
            """
        )
    ).fetchall()

    inserted = 0
    for engineer_id, tenant_id, raw in rows:
        if raw is None:
            continue
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            scheme = (item.get("scheme") or item.get("name") or "").strip()
            number = str(item.get("ticket_number") or item.get("number") or "").strip()
            if not scheme or not number:
                continue
            issuer = item.get("issuer")
            issued_at = item.get("issued_at") or item.get("issued")
            expires_at = item.get("expires_at") or item.get("expiry")
            bind.execute(
                sa.text(
                    """
                    INSERT INTO training_tickets (
                        engineer_id, scheme, ticket_number, issuer,
                        issued_at, expires_at, verify_state, evidence_id,
                        notes, tenant_id, created_at, updated_at
                    )
                    SELECT
                        :engineer_id, :scheme, :ticket_number, :issuer,
                        :issued_at, :expires_at, 'unverified', NULL,
                        'migrated_from_certifications_json', :tenant_id,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    WHERE NOT EXISTS (
                        SELECT 1 FROM training_tickets t
                        WHERE t.engineer_id = :engineer_id
                          AND t.scheme = :scheme
                          AND t.ticket_number = :ticket_number
                          AND t.tenant_id = :tenant_id
                    )
                    """
                ),
                {
                    "engineer_id": engineer_id,
                    "scheme": scheme[:100],
                    "ticket_number": number[:100],
                    "issuer": (str(issuer)[:200] if issuer else None),
                    "issued_at": issued_at,
                    "expires_at": expires_at,
                    "tenant_id": tenant_id,
                },
            )
            inserted += 1

    msg = f"training_tickets backfill from certifications_json attempted inserts={inserted}"
    logger.info(msg)
    print(msg)


def upgrade() -> None:
    if _table_exists("competency_requirements"):
        if not _has_column("competency_requirements", "role_key"):
            op.add_column(
                "competency_requirements",
                sa.Column("role_key", sa.String(length=100), nullable=True),
            )
            op.create_index(
                "ix_competency_requirements_role_key",
                "competency_requirements",
                ["role_key"],
            )
        if not _has_column("competency_requirements", "site"):
            op.add_column(
                "competency_requirements",
                sa.Column("site", sa.String(length=200), nullable=True),
            )
            op.create_index(
                "ix_competency_requirements_site",
                "competency_requirements",
                ["site"],
            )

    if not _table_exists("training_tickets"):
        op.create_table(
            "training_tickets",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("engineer_id", sa.Integer(), nullable=False),
            sa.Column("scheme", sa.String(length=100), nullable=False),
            sa.Column("ticket_number", sa.String(length=100), nullable=False),
            sa.Column("issuer", sa.String(length=200), nullable=True),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verify_state", sa.String(length=20), nullable=False, server_default="unverified"),
            sa.Column("evidence_id", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["engineer_id"], ["engineers.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["evidence_id"], ["evidence_assets.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_training_tickets_engineer_id", "training_tickets", ["engineer_id"])
        op.create_index("ix_training_tickets_scheme", "training_tickets", ["scheme"])
        op.create_index("ix_training_tickets_ticket_number", "training_tickets", ["ticket_number"])
        op.create_index("ix_training_tickets_expires_at", "training_tickets", ["expires_at"])
        op.create_index("ix_training_tickets_verify_state", "training_tickets", ["verify_state"])
        op.create_index("ix_training_tickets_evidence_id", "training_tickets", ["evidence_id"])
        op.create_index("ix_training_tickets_tenant_id", "training_tickets", ["tenant_id"])

    _backfill_tickets_from_certifications_json()


def downgrade() -> None:
    if _table_exists("training_tickets"):
        op.drop_table("training_tickets")

    if _table_exists("competency_requirements"):
        if _has_column("competency_requirements", "site"):
            op.drop_index("ix_competency_requirements_site", table_name="competency_requirements")
            op.drop_column("competency_requirements", "site")
        if _has_column("competency_requirements", "role_key"):
            op.drop_index("ix_competency_requirements_role_key", table_name="competency_requirements")
            op.drop_column("competency_requirements", "role_key")
