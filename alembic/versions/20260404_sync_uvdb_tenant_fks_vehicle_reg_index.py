"""Align PostgreSQL schema with ORM: UVDB tenant_id FKs + vehicle_reg unique index.

Revision ID: e1a2b3c4d5e6
Revises: d4e5f6a7b8c9
Create Date: 2026-04-04

Fixes alembic check drift:
- uvdb_section.tenant_id / uvdb_question.tenant_id → FK to tenants.id (columns added in 20260308 without FK)
- vehicle_registry: drop legacy unique constraint + redundant non-unique index; single unique index ix_vehicle_registry_vehicle_reg
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e1a2b3c4d5e6"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
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


def _has_tenant_fk(insp: sa.Inspector, table: str) -> bool:
    for fk in insp.get_foreign_keys(table):
        if fk.get("referred_table") != "tenants":
            continue
        cols = fk.get("constrained_columns") or []
        if cols == ["tenant_id"]:
            return True
    return False


def _driver_profiles_vehicle_reg_fk_name(insp: sa.Inspector) -> str | None:
    """FK from driver_profiles.allocated_vehicle_reg -> vehicle_registry.vehicle_reg blocks unique constraint drop."""
    if not _has_table(insp, "driver_profiles"):
        return None
    for fk in insp.get_foreign_keys("driver_profiles"):
        if fk.get("referred_table") != "vehicle_registry":
            continue
        if (fk.get("constrained_columns") or []) == ["allocated_vehicle_reg"] and (
            fk.get("referred_columns") or []
        ) == ["vehicle_reg"]:
            return fk.get("name")
    return None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    insp = _inspector()

    for tbl in ("uvdb_section", "uvdb_question"):
        if not _has_table(insp, tbl) or not _has_column(insp, tbl, "tenant_id"):
            continue
        if _has_tenant_fk(insp, tbl):
            continue
        op.create_foreign_key(
            f"fk_{tbl}_tenant_id_tenants",
            tbl,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _has_table(insp, "vehicle_registry"):
        return

    for uc in insp.get_unique_constraints("vehicle_registry"):
        cols = tuple(uc.get("column_names") or ())
        if cols == ("vehicle_reg",):
            op.drop_constraint(uc["name"], "vehicle_registry", type_="unique")

    for ix in insp.get_indexes("vehicle_registry"):
        if ix["name"] == "ix_vehicle_registry_vehicle_reg" and not ix.get("unique"):
            op.drop_index("ix_vehicle_registry_vehicle_reg", table_name="vehicle_registry")

    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_vehicle_registry_vehicle_reg ON vehicle_registry (vehicle_reg)"
    )

    if driver_vr_fk and _has_table(insp, "driver_profiles"):
        op.create_foreign_key(
            "driver_profiles_allocated_vehicle_reg_fkey",
            "driver_profiles",
            "vehicle_registry",
            ["allocated_vehicle_reg"],
            ["vehicle_reg"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    insp = _inspector()

    for tbl in ("uvdb_question", "uvdb_section"):
        if not _has_table(insp, tbl):
            continue
        for fk in insp.get_foreign_keys(tbl):
            if fk.get("name") == f"fk_{tbl}_tenant_id_tenants":
                op.drop_constraint(fk["name"], tbl, type_="foreignkey")

    # vehicle_registry: forward-only — restoring prior duplicate index + constraint risks re-introducing drift
