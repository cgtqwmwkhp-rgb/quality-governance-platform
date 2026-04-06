"""Unique CAPA per audit finding (tenant-scoped) for idempotent creation.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_capa_actions_tenant_audit_finding_source
        ON capa_actions (tenant_id, source_id)
        WHERE source_type = 'audit_finding' AND source_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS uq_capa_actions_tenant_audit_finding_source;")
