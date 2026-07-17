"""RR-W2: risk_notes + risk_activity_events for profile audit trail.

Revision ID: 20260723_rr_notes_act
Revises: 20260722_emp_pams
Create Date: 2026-07-23

Append-only risk commentary and typed activity events (assess, notes, etc.).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_rr_notes_act"
down_revision: Union[str, Sequence[str], None] = "20260722_emp_pams"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "risk_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["risk_id"], ["risks_v2.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_notes_tenant_id", "risk_notes", ["tenant_id"])
    op.create_index("ix_risk_notes_risk_id", "risk_notes", ["risk_id"])
    op.create_index("ix_risk_notes_created_by_id", "risk_notes", ["created_by_id"])
    op.create_index(
        "ix_risk_notes_tenant_risk_created",
        "risk_notes",
        ["tenant_id", "risk_id", "created_at"],
    )

    payload_type = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")
    op.create_table(
        "risk_activity_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload", payload_type, nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["risk_id"], ["risks_v2.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_activity_events_tenant_id", "risk_activity_events", ["tenant_id"])
    op.create_index("ix_risk_activity_events_risk_id", "risk_activity_events", ["risk_id"])
    op.create_index("ix_risk_activity_events_actor_id", "risk_activity_events", ["actor_id"])
    op.create_index("ix_risk_activity_events_event_type", "risk_activity_events", ["event_type"])
    op.create_index(
        "ix_risk_activity_events_tenant_risk_created",
        "risk_activity_events",
        ["tenant_id", "risk_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_risk_activity_events_tenant_risk_created", table_name="risk_activity_events")
    op.drop_index("ix_risk_activity_events_event_type", table_name="risk_activity_events")
    op.drop_index("ix_risk_activity_events_actor_id", table_name="risk_activity_events")
    op.drop_index("ix_risk_activity_events_risk_id", table_name="risk_activity_events")
    op.drop_index("ix_risk_activity_events_tenant_id", table_name="risk_activity_events")
    op.drop_table("risk_activity_events")

    op.drop_index("ix_risk_notes_tenant_risk_created", table_name="risk_notes")
    op.drop_index("ix_risk_notes_created_by_id", table_name="risk_notes")
    op.drop_index("ix_risk_notes_risk_id", table_name="risk_notes")
    op.drop_index("ix_risk_notes_tenant_id", table_name="risk_notes")
    op.drop_table("risk_notes")
