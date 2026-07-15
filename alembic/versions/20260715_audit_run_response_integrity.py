"""Wave1a: audit response uniqueness + audit_runs asset/engineer FKs.

Revision ID: 20260715_audit_db_integrity
Revises: 20260714_e0_promote_async
Create Date: 2026-07-15

- Deduplicate audit_responses on (run_id, question_id), keeping max(id)
- Enforce unique constraint/index uq_audit_responses_run_question
- Add nullable audit_runs.asset_id → assets.id (ON DELETE SET NULL)
- Add nullable audit_runs.engineer_id → engineers.id (ON DELETE SET NULL)
- Add composite indexes (tenant_id, asset_id) / (tenant_id, engineer_id)
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_audit_db_integrity"
down_revision: Union[str, Sequence[str], None] = "20260714_e0_promote_async"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UQ_AUDIT_RESPONSES = "uq_audit_responses_run_question"
IX_TENANT_ASSET = "ix_audit_runs_tenant_asset"
IX_TENANT_ENGINEER = "ix_audit_runs_tenant_engineer"
FK_ASSET = "fk_audit_runs_asset_id"
FK_ENGINEER = "fk_audit_runs_engineer_id"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return column_name in {column["name"] for column in _inspector().get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def _index_is_unique(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    for index in _inspector().get_indexes(table_name):
        if index["name"] == index_name:
            return bool(index.get("unique"))
    return False


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(
        constraint.get("name") == constraint_name for constraint in _inspector().get_unique_constraints(table_name)
    )


def _has_foreign_key(table_name: str, constraint_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(fk.get("name") == constraint_name for fk in _inspector().get_foreign_keys(table_name))


def _dedupe_audit_responses() -> None:
    """Keep max(id) per (run_id, question_id); Postgres DELETE ... USING."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("""
                DELETE FROM audit_responses AS older
                USING audit_responses AS newer
                WHERE older.run_id = newer.run_id
                  AND older.question_id = newer.question_id
                  AND older.id < newer.id
                """))
        return

    # SQLite / other: CTE delete of non-max ids (no DELETE ... USING)
    op.execute(sa.text("""
            DELETE FROM audit_responses
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY run_id, question_id
                            ORDER BY id DESC
                        ) AS row_num
                    FROM audit_responses
                ) ranked
                WHERE row_num > 1
            )
            """))


def _ensure_audit_response_uniqueness() -> None:
    if not _table_exists("audit_responses"):
        return

    if _has_unique_constraint("audit_responses", UQ_AUDIT_RESPONSES):
        return
    if _index_is_unique("audit_responses", UQ_AUDIT_RESPONSES):
        return

    _dedupe_audit_responses()

    # Legacy 20260227 may have created a non-unique index under this name when
    # duplicates blocked UNIQUE creation — drop it before enforcing uniqueness.
    if _has_index("audit_responses", UQ_AUDIT_RESPONSES) and not _index_is_unique(
        "audit_responses", UQ_AUDIT_RESPONSES
    ):
        op.drop_index(UQ_AUDIT_RESPONSES, table_name="audit_responses")

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("audit_responses") as batch_op:
            batch_op.create_unique_constraint(
                UQ_AUDIT_RESPONSES,
                ["run_id", "question_id"],
            )
    else:
        op.create_unique_constraint(
            UQ_AUDIT_RESPONSES,
            "audit_responses",
            ["run_id", "question_id"],
        )


def _add_run_fk_column(
    column_name: str,
    referred_table: str,
    fk_name: str,
) -> None:
    if not _table_exists("audit_runs") or _has_column("audit_runs", column_name):
        return
    op.add_column("audit_runs", sa.Column(column_name, sa.Integer(), nullable=True))
    if not _has_foreign_key("audit_runs", fk_name):
        op.create_foreign_key(
            fk_name,
            "audit_runs",
            referred_table,
            [column_name],
            ["id"],
            ondelete="SET NULL",
        )


def upgrade() -> None:
    _ensure_audit_response_uniqueness()

    _add_run_fk_column("asset_id", "assets", FK_ASSET)
    _add_run_fk_column("engineer_id", "engineers", FK_ENGINEER)

    if _table_exists("audit_runs") and _has_column("audit_runs", "asset_id"):
        if not _has_index("audit_runs", IX_TENANT_ASSET):
            op.create_index(IX_TENANT_ASSET, "audit_runs", ["tenant_id", "asset_id"])
    if _table_exists("audit_runs") and _has_column("audit_runs", "engineer_id"):
        if not _has_index("audit_runs", IX_TENANT_ENGINEER):
            op.create_index(IX_TENANT_ENGINEER, "audit_runs", ["tenant_id", "engineer_id"])


def downgrade() -> None:
    if _table_exists("audit_runs"):
        if _has_index("audit_runs", IX_TENANT_ENGINEER):
            op.drop_index(IX_TENANT_ENGINEER, table_name="audit_runs")
        if _has_index("audit_runs", IX_TENANT_ASSET):
            op.drop_index(IX_TENANT_ASSET, table_name="audit_runs")

        if _has_column("audit_runs", "engineer_id"):
            if _has_foreign_key("audit_runs", FK_ENGINEER):
                op.drop_constraint(FK_ENGINEER, "audit_runs", type_="foreignkey")
            op.drop_column("audit_runs", "engineer_id")
        if _has_column("audit_runs", "asset_id"):
            if _has_foreign_key("audit_runs", FK_ASSET):
                op.drop_constraint(FK_ASSET, "audit_runs", type_="foreignkey")
            op.drop_column("audit_runs", "asset_id")

    if not _table_exists("audit_responses"):
        return

    if _has_unique_constraint("audit_responses", UQ_AUDIT_RESPONSES):
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table("audit_responses") as batch_op:
                batch_op.drop_constraint(UQ_AUDIT_RESPONSES, type_="unique")
        else:
            op.drop_constraint(UQ_AUDIT_RESPONSES, "audit_responses", type_="unique")
    elif _has_index("audit_responses", UQ_AUDIT_RESPONSES):
        op.drop_index(UQ_AUDIT_RESPONSES, table_name="audit_responses")
