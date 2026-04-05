"""Align information_assets table name and columns with SQLAlchemy models.

Revision ID: a8b9c0d1e2f3
Revises: e1a2b3c4d5e6
Create Date: 2026-04-05

The initial ISO 27001 migration created ``information_asset`` (singular) while
``InformationAsset`` maps to ``information_assets`` (plural). That mismatch
caused runtime failures on routes touching the register. This revision renames
the table and adds nullable columns present on the ORM but missing from the
original DDL (tenant_id and lifecycle/cost fields).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "e1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(insp: sa.Inspector, name: str) -> bool:
    return insp.has_table(name)


def _has_column(insp: sa.Inspector, table: str, column: str) -> bool:
    if not _has_table(insp, table):
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = _inspector()

    if bind.dialect.name == "postgresql":
        if _has_table(insp, "information_asset") and not _has_table(insp, "information_assets"):
            op.rename_table("information_asset", "information_assets")
            insp = _inspector()

    if not _has_table(insp, "information_assets"):
        return

    if not _has_column(insp, "information_assets", "tenant_id"):
        op.add_column("information_assets", sa.Column("tenant_id", sa.Integer(), nullable=True))
        if _has_table(insp, "tenants"):
            op.create_foreign_key(
                "fk_information_assets_tenant_id_tenants",
                "information_assets",
                "tenants",
                ["tenant_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if bind.dialect.name == "postgresql":
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_information_assets_tenant_id ON information_assets (tenant_id)"
            )
        insp = _inspector()

    extra_cols: tuple[tuple[str, sa.Column], ...] = (
        ("replacement_cost", sa.Column("replacement_cost", sa.Float(), nullable=True)),
        ("acquisition_date", sa.Column("acquisition_date", sa.DateTime(), nullable=True)),
        ("disposal_date", sa.Column("disposal_date", sa.DateTime(), nullable=True)),
        ("disposal_method", sa.Column("disposal_method", sa.String(100), nullable=True)),
    )
    for col_name, col in extra_cols:
        if not _has_column(insp, "information_assets", col_name):
            op.add_column("information_assets", col)
        insp = _inspector()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    insp = _inspector()
    if not _has_table(insp, "information_assets"):
        return

    for fk in insp.get_foreign_keys("information_assets"):
        if fk.get("name") == "fk_information_assets_tenant_id_tenants":
            op.drop_constraint(fk["name"], "information_assets", type_="foreignkey")

    op.execute("DROP INDEX IF EXISTS ix_information_assets_tenant_id")

    for col in ("disposal_method", "disposal_date", "acquisition_date", "replacement_cost", "tenant_id"):
        if _has_column(insp, "information_assets", col):
            op.drop_column("information_assets", col)
        insp = _inspector()

    if _has_table(insp, "information_assets") and not _has_table(insp, "information_asset"):
        op.rename_table("information_assets", "information_asset")
