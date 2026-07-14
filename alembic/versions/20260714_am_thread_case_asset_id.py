"""AM-THREAD: nullable asset_id FK on incidents / near_misses / RTAs.

Revision ID: 20260714_am_thread
Revises: 20260714_safety_am_model
Create Date: 2026-07-14

Adds golden-thread link from safety cases to assets.id.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_am_thread"
down_revision: Union[str, Sequence[str], None] = "20260714_safety_am_model"
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


def _add_asset_id(table_name: str, fk_name: str, index_name: str) -> None:
    if not _table_exists(table_name) or _has_column(table_name, "asset_id"):
        return
    op.add_column(table_name, sa.Column("asset_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        fk_name,
        table_name,
        "assets",
        ["asset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(index_name, table_name, ["asset_id"])


def _drop_asset_id(table_name: str, fk_name: str, index_name: str) -> None:
    if not _table_exists(table_name) or not _has_column(table_name, "asset_id"):
        return
    op.drop_index(index_name, table_name=table_name)
    op.drop_constraint(fk_name, table_name, type_="foreignkey")
    op.drop_column(table_name, "asset_id")


def upgrade() -> None:
    _add_asset_id("incidents", "fk_incidents_asset_id", "ix_incidents_asset_id")
    _add_asset_id("near_misses", "fk_near_misses_asset_id", "ix_near_misses_asset_id")
    _add_asset_id(
        "road_traffic_collisions",
        "fk_road_traffic_collisions_asset_id",
        "ix_road_traffic_collisions_asset_id",
    )


def downgrade() -> None:
    _drop_asset_id(
        "road_traffic_collisions",
        "fk_road_traffic_collisions_asset_id",
        "ix_road_traffic_collisions_asset_id",
    )
    _drop_asset_id("near_misses", "fk_near_misses_asset_id", "ix_near_misses_asset_id")
    _drop_asset_id("incidents", "fk_incidents_asset_id", "ix_incidents_asset_id")
