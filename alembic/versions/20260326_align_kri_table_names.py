"""Align legacy and enterprise KRI table names with the model layer.

Revision ID: 20260326_align_kri_tables
Revises: 20260326_assurance_foundation
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260326_align_kri_tables"
down_revision: Union[str, None] = "20260326_assurance_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in _inspector().get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def _rename_index(table_name: str, old_name: str, new_name: str) -> None:
    if not old_name or old_name == new_name:
        return
    if op.get_bind().dialect.name == "sqlite":
        index = next(
            (candidate for candidate in _inspector().get_indexes(table_name) if candidate["name"] == old_name),
            None,
        )
        if not index:
            return
        op.create_index(
            new_name,
            table_name,
            index["column_names"],
            unique=index.get("unique", False),
        )
        op.drop_index(old_name, table_name=table_name)
        return
    op.execute(sa.text(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"'))


def _rename_legacy_kri_table() -> None:
    if not _table_exists("key_risk_indicators") or _has_column("key_risk_indicators", "risk_id"):
        return
    if _table_exists("legacy_key_risk_indicators"):
        return

    op.rename_table("key_risk_indicators", "legacy_key_risk_indicators")
    if _index_exists("legacy_key_risk_indicators", "ix_key_risk_indicators_tenant_id"):
        _rename_index(
            "legacy_key_risk_indicators",
            "ix_key_risk_indicators_tenant_id",
            "ix_legacy_key_risk_indicators_tenant_id",
        )


def _promote_enterprise_kri_table() -> None:
    if not _table_exists("enterprise_key_risk_indicators"):
        return
    if _table_exists("key_risk_indicators"):
        return

    op.rename_table("enterprise_key_risk_indicators", "key_risk_indicators")


def _ensure_enterprise_kri_tenant_column() -> None:
    if not _table_exists("key_risk_indicators") or _has_column("key_risk_indicators", "code"):
        return

    if not _has_column("key_risk_indicators", "tenant_id"):
        op.add_column("key_risk_indicators", sa.Column("tenant_id", sa.Integer(), nullable=True))

    if not _index_exists("key_risk_indicators", "ix_key_risk_indicators_tenant_id"):
        op.create_index("ix_key_risk_indicators_tenant_id", "key_risk_indicators", ["tenant_id"])


def upgrade() -> None:
    _rename_legacy_kri_table()
    _promote_enterprise_kri_table()
    _ensure_enterprise_kri_tenant_column()


def downgrade() -> None:
    if _table_exists("key_risk_indicators") and _has_column("key_risk_indicators", "risk_id"):
        if _index_exists("key_risk_indicators", "ix_key_risk_indicators_tenant_id"):
            op.drop_index("ix_key_risk_indicators_tenant_id", table_name="key_risk_indicators")
        if _has_column("key_risk_indicators", "tenant_id"):
            op.drop_column("key_risk_indicators", "tenant_id")
        if not _table_exists("enterprise_key_risk_indicators"):
            op.rename_table("key_risk_indicators", "enterprise_key_risk_indicators")

    if _table_exists("legacy_key_risk_indicators") and not _table_exists("key_risk_indicators"):
        if _index_exists("legacy_key_risk_indicators", "ix_legacy_key_risk_indicators_tenant_id"):
            _rename_index(
                "legacy_key_risk_indicators",
                "ix_legacy_key_risk_indicators_tenant_id",
                "ix_key_risk_indicators_tenant_id",
            )
        op.rename_table("legacy_key_risk_indicators", "key_risk_indicators")
