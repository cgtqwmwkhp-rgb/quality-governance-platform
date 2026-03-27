"""Add governed runner-sheet tables for cases.

Revision ID: 20260324_case_runner_sheets
Revises: 20260322_workforce_resp_uniques
Create Date: 2026-03-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260324_case_runner_sheets"
down_revision: Union[str, None] = "20260322_workforce_resp_uniques"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_timestamp_default() -> sa.TextClause:
    return sa.text("CURRENT_TIMESTAMP")


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_table("incident_running_sheet_entries"):
        op.create_table(
            "incident_running_sheet_entries",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
            sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("entry_type", sa.String(50), nullable=False, server_default="note"),
            sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("author_email", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_table("complaint_running_sheet_entries"):
        op.create_table(
            "complaint_running_sheet_entries",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
            sa.Column("complaint_id", sa.Integer(), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("entry_type", sa.String(50), nullable=False, server_default="note"),
            sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("author_email", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_table("near_miss_running_sheet_entries"):
        op.create_table(
            "near_miss_running_sheet_entries",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
            sa.Column("near_miss_id", sa.Integer(), sa.ForeignKey("near_misses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("entry_type", sa.String(50), nullable=False, server_default="note"),
            sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("author_email", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.PrimaryKeyConstraint("id"),
        )
    if _has_table("rta_running_sheet_entries") and not _has_column("rta_running_sheet_entries", "tenant_id"):
        op.add_column("rta_running_sheet_entries", sa.Column("tenant_id", sa.Integer(), nullable=True))
    if _has_table("rta_running_sheet_entries") and _has_column("rta_running_sheet_entries", "tenant_id"):
        op.execute(
            """
            UPDATE rta_running_sheet_entries
            SET tenant_id = (
                SELECT road_traffic_collisions.tenant_id
                FROM road_traffic_collisions
                WHERE road_traffic_collisions.id = rta_running_sheet_entries.rta_id
            )
            WHERE tenant_id IS NULL
              AND EXISTS (
                  SELECT 1
                  FROM road_traffic_collisions
                  WHERE road_traffic_collisions.id = rta_running_sheet_entries.rta_id
              )
            """
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incident_running_sheet_incident_id "
        "ON incident_running_sheet_entries(incident_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incident_running_sheet_created " "ON incident_running_sheet_entries(created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inc_run_sheet_tenant_incident "
        "ON incident_running_sheet_entries(tenant_id, incident_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_complaint_running_sheet_complaint_id "
        "ON complaint_running_sheet_entries(complaint_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_complaint_running_sheet_created "
        "ON complaint_running_sheet_entries(created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cmp_run_sheet_tenant_complaint "
        "ON complaint_running_sheet_entries(tenant_id, complaint_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_near_miss_running_sheet_near_miss_id "
        "ON near_miss_running_sheet_entries(near_miss_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_near_miss_running_sheet_created "
        "ON near_miss_running_sheet_entries(created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_nm_run_sheet_tenant_near_miss "
        "ON near_miss_running_sheet_entries(tenant_id, near_miss_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_rta_running_sheet_tenant ON rta_running_sheet_entries(tenant_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_rta_running_sheet_tenant_rta " "ON rta_running_sheet_entries(tenant_id, rta_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rta_running_sheet_tenant_rta")
    op.execute("DROP INDEX IF EXISTS ix_rta_running_sheet_tenant")
    if _has_table("rta_running_sheet_entries") and _has_column("rta_running_sheet_entries", "tenant_id"):
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table("rta_running_sheet_entries") as batch_op:
                batch_op.drop_column("tenant_id")
        else:
            op.drop_column("rta_running_sheet_entries", "tenant_id")
    if _has_table("near_miss_running_sheet_entries"):
        op.drop_table("near_miss_running_sheet_entries")
    if _has_table("complaint_running_sheet_entries"):
        op.drop_table("complaint_running_sheet_entries")
    if _has_table("incident_running_sheet_entries"):
        op.drop_table("incident_running_sheet_entries")
