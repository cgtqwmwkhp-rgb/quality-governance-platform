"""Fix evidence_asset.source_id type from Integer to String(36).

Revision ID: 20260302_ev_src_str
Revises: 20260302_capa_src_ref
Create Date: 2026-03-02 14:00:00.000000

Assessment and induction runs use UUID string primary keys, so source_id
must be String(36) to reference them without silent truncation / type errors.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260302_ev_src_str"
down_revision = "20260302_capa_src_ref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("evidence_assets") as batch_op:
            batch_op.alter_column(
                "source_id",
                existing_type=sa.Integer(),
                type_=sa.String(36),
                existing_nullable=False,
            )
        return

    op.alter_column(
        "evidence_assets",
        "source_id",
        existing_type=sa.Integer(),
        type_=sa.String(36),
        existing_nullable=False,
        postgresql_using="source_id::varchar(36)",
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("evidence_assets") as batch_op:
            batch_op.alter_column(
                "source_id",
                existing_type=sa.String(36),
                type_=sa.Integer(),
                existing_nullable=False,
            )
        return

    op.alter_column(
        "evidence_assets",
        "source_id",
        existing_type=sa.String(36),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="source_id::integer",
    )
