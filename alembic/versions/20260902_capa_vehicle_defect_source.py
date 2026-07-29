"""Add CAPASource.vehicle_defect enum value.

Revision ID: 20260902_capa_vd_src
Revises: 20260903_app_lp_role
Create Date: 2026-09-02

``CAPASource.VEHICLE_DEFECT`` has been declared in ``src/domain/models/capa.py``
since the vehicle module landed, but no migration ever added the matching label
to the PostgreSQL ``capasource`` type. Every statement that binds
``'vehicle_defect'`` to ``capa_actions.source_type`` is therefore rejected by the
enum input parser before any row is examined — the executive dashboard's
vehicle-governance count 500s on an empty table, and the vehicle defect CAPA
pipeline cannot insert at all.

Adds 'vehicle_defect' to the PostgreSQL capasource enum (idempotent).
Note: ALTER TYPE ADD VALUE is irreversible in PostgreSQL.

This revision only adds the label; it never binds it. A new enum value cannot be
referenced in the transaction that added it unless the type was created in that
same transaction, and ``alembic upgrade head`` runs the whole chain in one
transaction. Any later revision that needs to filter on this label must cast the
column to text, as ``20260720_capa_src_chk`` does.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260902_capa_vd_src"
# Re-pointed 29/07 from 20260901_case_tenant_nn to the tip of the RLS least-privilege
# chain. This revision was written against the head that existed when the lane started,
# and three lanes have since extended that same head: #1409 added the attribution
# columns and foreign keys, and #1410 added the RLS GUC guard and the least-privilege
# role. Left as it was, this revision branched from a parent two steps back and gave the
# tree TWO heads, which makes `alembic upgrade head` — the exact command both
# deploy-staging.yml and deploy-production.yml run — fail with MultipleHeads and abort
# the deploy at the migration step. Nothing about this migration depends on either of
# those chains: it only adds a label to the capasource enum, and it neither creates a
# table that would need granting nor reads one that RLS protects, so the ordering is
# free and linearising costs nothing.
down_revision: Union[str, Sequence[str], None] = "20260903_app_lp_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'capasource'")).fetchone()
    if result:
        try:
            op.execute("ALTER TYPE capasource ADD VALUE IF NOT EXISTS 'vehicle_defect'")
        except Exception:
            pass


def downgrade() -> None:
    pass  # ALTER TYPE ADD VALUE cannot be reversed
