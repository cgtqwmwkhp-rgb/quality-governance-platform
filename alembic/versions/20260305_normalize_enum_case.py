"""Normalize enum VARCHAR columns to lowercase values.

Revision ID: 20260305_enum_case
Revises: 20260302_ev_src_str
Create Date: 2026-03-05

The initial schema migration created native PostgreSQL enum types with
UPPERCASE labels (e.g. 'DRAFT', 'SCHEDULED').  A later migration
(convert_enums_to_varchar) converted these columns to VARCHAR using
``column::text``, which preserved the UPPERCASE text.  The Python enum
classes however use lowercase values (e.g. 'draft', 'scheduled').
SQLAlchemy's ``Enum(native_enum=False)`` tries ``EnumClass(value)`` on
read, which raises ``ValueError`` for the uppercase values.

This migration normalises every affected column to lowercase so the
ORM can deserialise them correctly.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260305_enum_case"
down_revision: Union[str, None] = "20260303_feature_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENUM_COLUMNS = [
    ("incidents", "incident_type"),
    ("incidents", "severity"),
    ("incidents", "status"),
    ("incident_actions", "status"),
    ("road_traffic_collisions", "severity"),
    ("road_traffic_collisions", "status"),
    ("rta_actions", "status"),
    ("complaints", "complaint_type"),
    ("complaints", "priority"),
    ("complaints", "status"),
    ("complaint_actions", "status"),
    ("audit_runs", "status"),
    ("audit_findings", "status"),
    ("policies", "document_type"),
    ("policies", "status"),
    ("policy_versions", "status"),
    ("risks", "status"),
    ("investigation_runs", "assigned_entity_type"),
    ("investigation_runs", "status"),
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    for table, column in ENUM_COLUMNS:
        if not inspector.has_table(table):
            continue
        if column not in {col["name"] for col in inspector.get_columns(table)}:
            continue

        op.execute(
            sa.text(
                f"UPDATE {table} SET {column} = LOWER({column}) "
                f"WHERE {column} IS NOT NULL AND {column} <> LOWER({column})"
            )
        )


def downgrade() -> None:
    pass
