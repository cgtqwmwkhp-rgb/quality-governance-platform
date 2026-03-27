"""Add MFA-related columns to users table.

Revision ID: 20260222_user_mfa
Revises: 20260221_fk_indexes
Create Date: 2026-02-22

Adds totp_secret, mfa_enabled, and password_history columns to support
multi-factor authentication and password rotation tracking.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260222_user_mfa"
down_revision: Union[str, None] = "20260221_fk_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        inspector = sa.inspect(conn)
        if inspector.has_table("users"):
            existing_columns = {col["name"] for col in inspector.get_columns("users")}
            if "totp_secret" not in existing_columns:
                op.add_column("users", sa.Column("totp_secret", sa.String(length=64), nullable=True))
            if "mfa_enabled" not in existing_columns:
                op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=True, server_default=sa.text("false")))
            if "password_history" not in existing_columns:
                op.add_column("users", sa.Column("password_history", sa.Text(), nullable=True))
        return

    op.execute(
        "DO $$ BEGIN "
        "  IF NOT EXISTS ("
        "    SELECT 1 FROM information_schema.columns "
        "    WHERE table_name = 'users' AND column_name = 'totp_secret'"
        "  ) THEN "
        "    ALTER TABLE users ADD COLUMN totp_secret VARCHAR(64); "
        "  END IF; "
        "END $$"
    )
    op.execute(
        "DO $$ BEGIN "
        "  IF NOT EXISTS ("
        "    SELECT 1 FROM information_schema.columns "
        "    WHERE table_name = 'users' AND column_name = 'mfa_enabled'"
        "  ) THEN "
        "    ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN DEFAULT FALSE; "
        "  END IF; "
        "END $$"
    )
    op.execute(
        "DO $$ BEGIN "
        "  IF NOT EXISTS ("
        "    SELECT 1 FROM information_schema.columns "
        "    WHERE table_name = 'users' AND column_name = 'password_history'"
        "  ) THEN "
        "    ALTER TABLE users ADD COLUMN password_history TEXT; "
        "  END IF; "
        "END $$"
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        inspector = sa.inspect(conn)
        if inspector.has_table("users"):
            existing_columns = {col["name"] for col in inspector.get_columns("users")}
            for column in ("password_history", "mfa_enabled", "totp_secret"):
                if column in existing_columns:
                    op.drop_column("users", column)
        return

    op.execute(
        "ALTER TABLE users "
        "DROP COLUMN IF EXISTS totp_secret, "
        "DROP COLUMN IF EXISTS mfa_enabled, "
        "DROP COLUMN IF EXISTS password_history"
    )
