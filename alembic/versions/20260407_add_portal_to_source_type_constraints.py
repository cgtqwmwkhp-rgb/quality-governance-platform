"""Add 'portal' to incident and complaint source_type CHECK constraints.

Revision ID: portal_source_type_01
Revises: iso27001_schema_drift_02
Create Date: 2026-04-07

The employee portal route (src/api/routes/employee_portal.py) submits incidents
and complaints with source_type='portal', but the database CHECK constraints only
allow ('manual', 'email', 'api') for incidents and ('manual', 'email', 'api',
'phone') for complaints.  Every portal submission raises IntegrityError in both
SQLite (tests) and PostgreSQL (production).

Fix: drop the old constraints and recreate them with 'portal' included.
SQLite does not support ALTER TABLE DROP CONSTRAINT, so the migration is a no-op
for non-PostgreSQL dialects (the ORM model change propagates to the test DB on
table creation).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "portal_source_type_01"
down_revision: Union[str, None] = "iso27001_schema_drift_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    # Incidents: add 'portal' to ck_incident_source_type
    conn.execute(
        sa.text(
            "DO $$ BEGIN "
            "  ALTER TABLE incidents "
            "    DROP CONSTRAINT IF EXISTS ck_incident_source_type; "
            "EXCEPTION WHEN OTHERS THEN "
            "  RAISE NOTICE 'drop ck_incident_source_type: %', SQLERRM; "
            "END $$"
        )
    )
    conn.execute(
        sa.text(
            "DO $$ BEGIN "
            "  ALTER TABLE incidents "
            "    ADD CONSTRAINT ck_incident_source_type "
            "    CHECK (source_type IN (''manual'', ''email'', ''api'', ''portal'')); "
            "EXCEPTION WHEN OTHERS THEN "
            "  RAISE NOTICE 'add ck_incident_source_type: %', SQLERRM; "
            "END $$"
        )
    )

    # Complaints: add 'portal' to ck_complaint_source_type
    conn.execute(
        sa.text(
            "DO $$ BEGIN "
            "  ALTER TABLE complaints "
            "    DROP CONSTRAINT IF EXISTS ck_complaint_source_type; "
            "EXCEPTION WHEN OTHERS THEN "
            "  RAISE NOTICE 'drop ck_complaint_source_type: %', SQLERRM; "
            "END $$"
        )
    )
    conn.execute(
        sa.text(
            "DO $$ BEGIN "
            "  ALTER TABLE complaints "
            "    ADD CONSTRAINT ck_complaint_source_type "
            "    CHECK (source_type IN (''manual'', ''email'', ''api'', ''phone'', ''portal'')); "
            "EXCEPTION WHEN OTHERS THEN "
            "  RAISE NOTICE 'add ck_complaint_source_type: %', SQLERRM; "
            "END $$"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    # Incidents: revert to original constraint without 'portal'
    conn.execute(
        sa.text(
            "DO $$ BEGIN "
            "  ALTER TABLE incidents "
            "    DROP CONSTRAINT IF EXISTS ck_incident_source_type; "
            "EXCEPTION WHEN OTHERS THEN "
            "  RAISE NOTICE 'drop ck_incident_source_type: %', SQLERRM; "
            "END $$"
        )
    )
    conn.execute(
        sa.text(
            "DO $$ BEGIN "
            "  ALTER TABLE incidents "
            "    ADD CONSTRAINT ck_incident_source_type "
            "    CHECK (source_type IN (''manual'', ''email'', ''api'')); "
            "EXCEPTION WHEN OTHERS THEN "
            "  RAISE NOTICE 'add ck_incident_source_type: %', SQLERRM; "
            "END $$"
        )
    )

    # Complaints: revert to original constraint without 'portal'
    conn.execute(
        sa.text(
            "DO $$ BEGIN "
            "  ALTER TABLE complaints "
            "    DROP CONSTRAINT IF EXISTS ck_complaint_source_type; "
            "EXCEPTION WHEN OTHERS THEN "
            "  RAISE NOTICE 'drop ck_complaint_source_type: %', SQLERRM; "
            "END $$"
        )
    )
    conn.execute(
        sa.text(
            "DO $$ BEGIN "
            "  ALTER TABLE complaints "
            "    ADD CONSTRAINT ck_complaint_source_type "
            "    CHECK (source_type IN (''manual'', ''email'', ''api'', ''phone'')); "
            "EXCEPTION WHEN OTHERS THEN "
            "  RAISE NOTICE 'add ck_complaint_source_type: %', SQLERRM; "
            "END $$"
        )
    )
