"""Safety Asset Management model spine (AM-MODEL).

Revision ID: 20260714_safety_am_model
Revises: 20260714_merge_inc_cg_dv
Create Date: 2026-07-14

- Creates locations (site|workshop)
- Extends assets with location/vehicle/owner/expiry/photo evidence
- Creates asset_assignment_events (append-only)
- Seeds global SAFETY asset types (idempotent by name+category)
- Adds capa_actions.asset_id FK
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_safety_am_model"
down_revision: Union[str, Sequence[str], None] = "20260714_merge_inc_cg_dv"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return column_name in {column["name"] for column in _inspector().get_columns(table_name)}


def upgrade() -> None:
    if not _table_exists("locations"):
        op.create_table(
            "locations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("kind", sa.String(length=50), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["parent_id"], ["locations.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_locations_tenant_id", "locations", ["tenant_id"])
        op.create_index("ix_locations_kind", "locations", ["kind"])
        op.create_index("ix_locations_parent_id", "locations", ["parent_id"])
        op.create_index("ix_locations_created_at", "locations", ["created_at"])

    if _table_exists("assets"):
        if not _has_column("assets", "location_id"):
            op.add_column("assets", sa.Column("location_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_assets_location_id",
                "assets",
                "locations",
                ["location_id"],
                ["id"],
                ondelete="SET NULL",
            )
            op.create_index("ix_assets_location_id", "assets", ["location_id"])
        if not _has_column("assets", "vehicle_reg"):
            op.add_column("assets", sa.Column("vehicle_reg", sa.String(length=20), nullable=True))
            op.create_index("ix_assets_vehicle_reg", "assets", ["vehicle_reg"])
        if not _has_column("assets", "owner_user_id"):
            op.add_column("assets", sa.Column("owner_user_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_assets_owner_user_id",
                "assets",
                "users",
                ["owner_user_id"],
                ["id"],
                ondelete="SET NULL",
            )
            op.create_index("ix_assets_owner_user_id", "assets", ["owner_user_id"])
        if not _has_column("assets", "expiry_date"):
            op.add_column("assets", sa.Column("expiry_date", sa.DateTime(timezone=True), nullable=True))
            op.create_index("ix_assets_expiry_date", "assets", ["expiry_date"])
        if not _has_column("assets", "photo_evidence_id"):
            op.add_column("assets", sa.Column("photo_evidence_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_assets_photo_evidence_id",
                "assets",
                "evidence_assets",
                ["photo_evidence_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if not _table_exists("asset_assignment_events"):
        op.create_table(
            "asset_assignment_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("from_location_id", sa.Integer(), nullable=True),
            sa.Column("to_location_id", sa.Integer(), nullable=True),
            sa.Column("from_vehicle_reg", sa.String(length=20), nullable=True),
            sa.Column("to_vehicle_reg", sa.String(length=20), nullable=True),
            sa.Column("from_owner_user_id", sa.Integer(), nullable=True),
            sa.Column("to_owner_user_id", sa.Integer(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["from_location_id"], ["locations.id"]),
            sa.ForeignKeyConstraint(["to_location_id"], ["locations.id"]),
            sa.ForeignKeyConstraint(["from_owner_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["to_owner_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_asset_assignment_events_asset_id", "asset_assignment_events", ["asset_id"])
        op.create_index("ix_asset_assignment_events_tenant_id", "asset_assignment_events", ["tenant_id"])
        op.create_index("ix_asset_assignment_events_created_at", "asset_assignment_events", ["created_at"])

    if _table_exists("capa_actions") and not _has_column("capa_actions", "asset_id"):
        op.add_column("capa_actions", sa.Column("asset_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_capa_actions_asset_id",
            "capa_actions",
            "assets",
            ["asset_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_capa_actions_asset_id", "capa_actions", ["asset_id"])

    # Seed global SAFETY asset types (tenant_id NULL) if missing by name+category
    if _table_exists("asset_types"):
        bind = op.get_bind()
        seeds = (
            ("Engineer Tool", "Engineer tooling / PPE-adjacent equipment"),
            ("Fire Extinguisher", "Portable fire extinguisher"),
            ("First Aid Kit", "First aid kit / medical supplies"),
        )
        for name, description in seeds:
            exists = bind.execute(
                sa.text("""
                    SELECT 1 FROM asset_types
                    WHERE name = :name AND lower(category) = 'safety'
                    LIMIT 1
                    """),
                {"name": name},
            ).fetchone()
            if exists:
                continue
            bind.execute(
                sa.text("""
                    INSERT INTO asset_types
                        (category, name, description, is_active, tenant_id, created_at, updated_at)
                    VALUES
                        ('safety', :name, :description, true, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """),
                {"name": name, "description": description},
            )


def downgrade() -> None:
    if _has_column("capa_actions", "asset_id"):
        op.drop_index("ix_capa_actions_asset_id", table_name="capa_actions")
        op.drop_constraint("fk_capa_actions_asset_id", "capa_actions", type_="foreignkey")
        op.drop_column("capa_actions", "asset_id")

    if _table_exists("asset_assignment_events"):
        op.drop_table("asset_assignment_events")

    if _table_exists("assets"):
        if _has_column("assets", "photo_evidence_id"):
            op.drop_constraint("fk_assets_photo_evidence_id", "assets", type_="foreignkey")
            op.drop_column("assets", "photo_evidence_id")
        if _has_column("assets", "expiry_date"):
            op.drop_index("ix_assets_expiry_date", table_name="assets")
            op.drop_column("assets", "expiry_date")
        if _has_column("assets", "owner_user_id"):
            op.drop_index("ix_assets_owner_user_id", table_name="assets")
            op.drop_constraint("fk_assets_owner_user_id", "assets", type_="foreignkey")
            op.drop_column("assets", "owner_user_id")
        if _has_column("assets", "vehicle_reg"):
            op.drop_index("ix_assets_vehicle_reg", table_name="assets")
            op.drop_column("assets", "vehicle_reg")
        if _has_column("assets", "location_id"):
            op.drop_index("ix_assets_location_id", table_name="assets")
            op.drop_constraint("fk_assets_location_id", "assets", type_="foreignkey")
            op.drop_column("assets", "location_id")

    if _table_exists("locations"):
        op.drop_table("locations")
