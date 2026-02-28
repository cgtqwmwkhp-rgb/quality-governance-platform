"""Add data integrity constraints.

Revision ID: 20260221_integrity
Revises: 20260221_composite_idx
Create Date: 2026-02-21

Adds UNIQUE constraints, CHECK constraints on status fields,
and a version column for optimistic locking on frequently updated tables.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260221_integrity"
down_revision: Union[str, None] = "20260221_composite_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- UNIQUE constraints (wrapped in PL/pgSQL for subtransaction safety) ---
    for table, col, cname in [
        ("users", "email", "uq_users_email"),
        ("incidents", "reference_number", "uq_incidents_reference"),
        ("risks", "reference_number", "uq_risks_reference"),
        ("audits", "reference_number", "uq_audits_reference"),
        ("complaints", "reference_number", "uq_complaints_reference"),
    ]:
        conn.execute(sa.text(
            f"DO $$ BEGIN "
            f"  IF EXISTS (SELECT 1 FROM information_schema.columns "
            f"    WHERE table_name = '{table}' AND column_name = '{col}') "
            f"  AND NOT EXISTS (SELECT 1 FROM pg_constraint "
            f"    WHERE conname = '{cname}') THEN "
            f"    EXECUTE 'ALTER TABLE {table} "
            f"      ADD CONSTRAINT {cname} UNIQUE ({col})'; "
            f"  END IF; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'skip {cname}: %', SQLERRM; "
            f"END $$"
        ))

    # --- CHECK constraints on status fields ---
    for table, cname, condition in [
        ("incidents", "ck_incidents_status",
         "status IN (''reported'', ''under_investigation'', ''pending_actions'', ''actions_in_progress'', ''pending_review'', ''closed'')"),
        ("risks", "ck_risks_status",
         "status IN (''open'', ''mitigating'', ''accepted'', ''closed'')"),
        ("audits", "ck_audits_status",
         "status IN (''planned'', ''in_progress'', ''completed'', ''cancelled'')"),
        ("complaints", "ck_complaints_status",
         "status IN (''received'', ''acknowledged'', ''under_investigation'', ''pending_response'', ''awaiting_customer'', ''resolved'', ''closed'', ''escalated'')"),
    ]:
        conn.execute(sa.text(
            f"DO $$ BEGIN "
            f"  IF EXISTS (SELECT 1 FROM information_schema.tables "
            f"    WHERE table_name = '{table}') "
            f"  AND NOT EXISTS (SELECT 1 FROM pg_constraint "
            f"    WHERE conname = '{cname}') THEN "
            f"    EXECUTE 'ALTER TABLE {table} "
            f"      ADD CONSTRAINT {cname} CHECK ({condition})'; "
            f"  END IF; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'skip {cname}: %', SQLERRM; "
            f"END $$"
        ))

    # --- Version column for optimistic locking ---
    for table in ("incidents", "risks", "audits", "complaints"):
        conn.execute(sa.text(
            f"DO $$ BEGIN "
            f"  IF EXISTS (SELECT 1 FROM information_schema.tables "
            f"    WHERE table_name = '{table}') "
            f"  AND NOT EXISTS (SELECT 1 FROM information_schema.columns "
            f"    WHERE table_name = '{table}' AND column_name = 'version') THEN "
            f"    EXECUTE 'ALTER TABLE {table} "
            f"      ADD COLUMN version INTEGER NOT NULL DEFAULT 1'; "
            f"  END IF; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'skip version for {table}: %', SQLERRM; "
            f"END $$"
        ))


def downgrade() -> None:
    conn = op.get_bind()

    for table in ("complaints", "audits", "risks", "incidents"):
        if _table_has_column(conn, table, "version"):
            op.drop_column(table, "version")

    for name in (
        "ck_complaints_status",
        "ck_audits_status",
        "ck_risks_status",
        "ck_incidents_status",
    ):
        try:
            op.drop_constraint(name, name.split("_")[1] + "s")
        except Exception:
            pass

    for name in (
        "uq_complaints_reference",
        "uq_audits_reference",
        "uq_risks_reference",
        "uq_incidents_reference",
        "uq_users_email",
    ):
        try:
            table = name.replace("uq_", "").rsplit("_", 1)[0]
            op.drop_constraint(name, table)
        except Exception:
            pass
