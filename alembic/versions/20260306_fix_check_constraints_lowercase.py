"""Fix CHECK constraints to accept lowercase enum values.

Revision ID: 20260306_ck_lower
Revises: 20260305_enum_case
Create Date: 2026-03-06

The 20260221_add_data_integrity_constraints migration added CHECK constraints
with UPPERCASE values (e.g. 'REPORTED').  The 20260305_normalize_enum_case
migration lowercased all existing data, and the CaseInsensitiveEnum
TypeDecorator writes lowercase.  This migration drops the old UPPERCASE
constraints and recreates them with lowercase values so new inserts succeed.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260306_ck_lower"
down_revision: Union[str, None] = "20260305_enum_case"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINTS = [
    (
        "incidents",
        "ck_incidents_status",
        "status IN ('reported','under_investigation','pending_actions',"
        "'actions_in_progress','pending_review','closed')",
    ),
    (
        "risks",
        "ck_risks_status",
        "status IN ('open','mitigating','accepted','closed')",
    ),
    (
        "audits",
        "ck_audits_status",
        "status IN ('planned','in_progress','completed','cancelled')",
    ),
    (
        "complaints",
        "ck_complaints_status",
        "status IN ('received','acknowledged','under_investigation',"
        "'pending_response','awaiting_customer','resolved','closed','escalated')",
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for table, cname, condition in CONSTRAINTS:
        conn.execute(
            sa.text(
                f"DO $$ BEGIN "
                f"  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{cname}') THEN "
                f"    EXECUTE 'ALTER TABLE {table} DROP CONSTRAINT {cname}'; "
                f"  END IF; "
                f"EXCEPTION WHEN OTHERS THEN "
                f"  RAISE NOTICE 'drop {cname}: %', SQLERRM; "
                f"END $$"
            )
        )
        conn.execute(
            sa.text(
                f"DO $$ BEGIN "
                f"  IF EXISTS (SELECT 1 FROM information_schema.tables "
                f"    WHERE table_name = '{table}') THEN "
                f"    EXECUTE 'ALTER TABLE {table} "
                f"      ADD CONSTRAINT {cname} CHECK ({condition})'; "
                f"  END IF; "
                f"EXCEPTION WHEN OTHERS THEN "
                f"  RAISE NOTICE 'add {cname}: %', SQLERRM; "
                f"END $$"
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    for table, cname, _ in CONSTRAINTS:
        conn.execute(
            sa.text(
                f"DO $$ BEGIN "
                f"  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{cname}') THEN "
                f"    EXECUTE 'ALTER TABLE {table} DROP CONSTRAINT {cname}'; "
                f"  END IF; "
                f"EXCEPTION WHEN OTHERS THEN "
                f"  RAISE NOTICE 'drop {cname}: %', SQLERRM; "
                f"END $$"
            )
        )
