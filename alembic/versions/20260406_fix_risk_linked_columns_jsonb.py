"""Change linked_audits/actions/incidents on risks_v2 from JSON to JSONB.

PostgreSQL JSON does not support the @> containment operator used by
SQLAlchemy's .contains() method. JSONB is required for these queries,
which are exercised during external audit promotion when checking for
existing risk entries by linked finding reference.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-04-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for col in ("linked_audits", "linked_actions", "linked_incidents"):
        op.execute(
            sa.text(
                f"ALTER TABLE risks_v2 "
                f"ALTER COLUMN {col} TYPE JSONB USING {col}::jsonb"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for col in ("linked_audits", "linked_actions", "linked_incidents"):
        op.execute(
            sa.text(
                f"ALTER TABLE risks_v2 "
                f"ALTER COLUMN {col} TYPE JSON USING {col}::json"
            )
        )
