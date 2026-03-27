"""Extend CAPASource enum with workforce development values.

Revision ID: 20260302_capa_enum
Revises: 20260302_wdp_cols
Create Date: 2026-03-02 10:10:00.000000

Adds JOB_ASSESSMENT, INDUCTION, LOLER_EXAMINATION to the CAPASource enum.
Note: ALTER TYPE ADD VALUE is irreversible in PostgreSQL.
"""

from alembic import op

revision = "20260302_capa_enum"
down_revision = "20260302_wdp_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    # CAPASource uses native PostgreSQL enum via Enum() (not native_enum=False)
    # so we need ALTER TYPE. If the column uses String storage (native_enum=False),
    # no ALTER TYPE is needed -- the Python enum is sufficient.
    # The capa.py model uses Enum(CAPAType) without native_enum=False, so we
    # check and add if needed.
    # Check if enum type exists (it may use string storage)
    result = conn.execute(
        __import__("sqlalchemy").text(
            "SELECT 1 FROM pg_type WHERE typname = 'capasource'"
        )
    ).fetchone()
    if result:
        for val in ("job_assessment", "induction", "loler_examination"):
            try:
                op.execute(f"ALTER TYPE capasource ADD VALUE IF NOT EXISTS '{val}'")
            except Exception:
                pass  # Value already exists or string-based enum


def downgrade() -> None:
    pass  # ALTER TYPE ADD VALUE cannot be reversed
