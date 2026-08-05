"""Create sso_provisioning_requests (additive schema only).

Revision ID: 20261012_sso_prov_req
Revises: 20260914_cs_notif_dedupe
Create Date: 2026-10-12

Additive table for the SSO pending-approval queue. ``tenant_id`` is NOT NULL and
holds the *candidate* tenant — never a tenant-less pending row. Status lives
here, never on ``users`` (FORCE RLS + AuditLogEntry.tenant_id NOT NULL make a
tenant-less pending user unauditable and permanently locked out).

RLS hardening is a separate revision (``20261012_rls_sso_prov``) so this table
can land alone; see the design note in that file and
``tests/unit/test_run026_rls_least_privilege.py``.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261012_sso_prov_req"
down_revision: Union[str, Sequence[str], None] = "20260914_cs_notif_dedupe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TABLE = "sso_provisioning_requests"

# Held as literals and asserted against the ORM in unit tests so the migration
# describes the database at this revision and does not change meaning when the
# model file is edited later (same pattern as 20260914_cs_notif_dedupe).
PENDING_EMAIL_INDEX_DDL = (
    f"CREATE UNIQUE INDEX ux_sso_prov_pending_email ON {TABLE} " "(tenant_id, lower(email)) WHERE status = 'pending'"
)
PENDING_OID_INDEX_DDL = (
    f"CREATE UNIQUE INDEX ux_sso_prov_pending_oid ON {TABLE} "
    "(azure_oid) WHERE status = 'pending' AND azure_oid IS NOT NULL"
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return bool(
            bind.execute(
                sa.text("SELECT 1 FROM pg_class WHERE relkind = 'i' AND relname = :name"),
                {"name": index_name},
            ).fetchone()
        )
    # SQLite / others: walk the table's indexes when the table exists.
    if not _table_exists(TABLE):
        return False
    return any(idx["name"] == index_name for idx in _inspector().get_indexes(TABLE))


def upgrade() -> None:
    if _table_exists(TABLE):
        logger.info("%s: %s already present — skipping create", revision, TABLE)
    else:
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("azure_oid", sa.String(length=36), nullable=True),
            sa.Column("first_name", sa.String(length=100), nullable=False),
            sa.Column("last_name", sa.String(length=100), nullable=False),
            sa.Column("job_title", sa.String(length=100), nullable=True),
            sa.Column("department", sa.String(length=100), nullable=True),
            sa.Column("reference", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
            sa.Column("match_basis", sa.String(length=40), nullable=False),
            sa.Column("attempt_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
            # TIMESTAMP WITHOUT TIME ZONE — NaiveUTCDateTime on the ORM side.
            sa.Column("first_attempt_at", sa.DateTime(), nullable=False),
            sa.Column("last_attempt_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column("decided_by_id", sa.Integer(), nullable=True),
            sa.Column("decision_reason", sa.String(length=500), nullable=True),
            sa.Column("created_user_id", sa.Integer(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'approved', 'rejected', 'expired', 'superseded')",
                name="ck_sso_provisioning_requests_status",
            ),
            sa.CheckConstraint(
                "match_basis IN ('deployment_default', 'email_domain_allowlist')",
                name="ck_sso_provisioning_requests_match_basis",
            ),
            sa.CheckConstraint(
                "attempt_count >= 1",
                name="ck_sso_provisioning_requests_attempt_count",
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["decided_by_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["created_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_sso_provisioning_requests_tenant_id", TABLE, ["tenant_id"])
        # unique=True + index=True on the ORM renders as one unique index named
        # ix_<table>_<column> (same note as compliance_requirements.external_id).
        op.create_index("ix_sso_provisioning_requests_reference", TABLE, ["reference"], unique=True)
        op.create_index("ix_sso_prov_tenant_status", TABLE, ["tenant_id", "status"])
        op.create_index("ix_sso_provisioning_requests_created_at", TABLE, ["created_at"])

    if op.get_bind().dialect.name == "postgresql":
        if not _index_exists("ux_sso_prov_pending_email"):
            op.execute(sa.text(PENDING_EMAIL_INDEX_DDL))
        if not _index_exists("ux_sso_prov_pending_oid"):
            op.execute(sa.text(PENDING_OID_INDEX_DDL))
    else:
        # Non-Postgres (SQLite unit/dev): recreate the partial unique indexes via
        # SQLAlchemy so create_all / alembic check stay aligned with the ORM.
        if not _index_exists("ux_sso_prov_pending_email"):
            op.create_index(
                "ux_sso_prov_pending_email",
                TABLE,
                ["tenant_id", sa.text("lower(email)")],
                unique=True,
                sqlite_where=sa.text("status = 'pending'"),
            )
        if not _index_exists("ux_sso_prov_pending_oid"):
            op.create_index(
                "ux_sso_prov_pending_oid",
                TABLE,
                ["azure_oid"],
                unique=True,
                sqlite_where=sa.text("status = 'pending' AND azure_oid IS NOT NULL"),
            )


def downgrade() -> None:
    if not _table_exists(TABLE):
        return
    for name in (
        "ux_sso_prov_pending_oid",
        "ux_sso_prov_pending_email",
        "ix_sso_provisioning_requests_created_at",
        "ix_sso_prov_tenant_status",
        "ix_sso_provisioning_requests_reference",
        "ix_sso_provisioning_requests_tenant_id",
    ):
        if _index_exists(name):
            op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
