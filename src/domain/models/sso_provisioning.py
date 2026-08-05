"""SSO provisioning approval-queue models.

A row here is a *candidate* account, not a user. ``users`` stays under FORCE RLS
with a NOT NULL ``AuditLogEntry.tenant_id``, so a tenant-less pending user cannot
be audited and would be permanently locked out under the tenant_isolation
predicate. Binding ``tenant_id`` NOT NULL at creation is therefore load-bearing,
not decorative: it is what lets this table join ``RLS_TABLES`` and what
``scripts/validate_tenant_id_not_null.py`` requires of every new owned table.

Status lives here, never on ``users``. Downstream API / service work (approve,
reject, expiry sweep) is deliberately out of this schema PR.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.audit_log import NaiveUTCDateTime
from src.domain.models.base import AuditTrailMixin, Base, CaseInsensitiveEnum, DataClassification, TimestampMixin


class SSOProvisioningStatus(str, Enum):
    """Lifecycle of an SSO provisioning request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class SSOProvisioningMatchBasis(str, Enum):
    """How the candidate tenant was resolved at request creation."""

    DEPLOYMENT_DEFAULT = "deployment_default"
    EMAIL_DOMAIN_ALLOWLIST = "email_domain_allowlist"


_STATUS_VALUES = ", ".join(f"'{m.value}'" for m in SSOProvisioningStatus)
_MATCH_BASIS_VALUES = ", ".join(f"'{m.value}'" for m in SSOProvisioningMatchBasis)


class SSOProvisioningRequest(Base, TimestampMixin, AuditTrailMixin):
    """Pending (or decided) request to provision a user from an SSO assertion.

    ``tenant_id`` is the *candidate* tenant — the organisation that will own the
    user if approved. The column is named ``tenant_id`` (not
    ``candidate_tenant_id``) so ``TENANT_ISOLATION_PREDICATE`` and
    ``apply_tenant_filter`` work without special cases.
    """

    __tablename__ = "sso_provisioning_requests"
    __data_classification__ = DataClassification.C3_CONFIDENTIAL
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_STATUS_VALUES})",
            name="ck_sso_provisioning_requests_status",
        ),
        CheckConstraint(
            f"match_basis IN ({_MATCH_BASIS_VALUES})",
            name="ck_sso_provisioning_requests_match_basis",
        ),
        CheckConstraint(
            "attempt_count >= 1",
            name="ck_sso_provisioning_requests_attempt_count",
        ),
        # One open request per (tenant, email). A repeat SSO attempt must update
        # attempt_count / last_attempt_at rather than insert a second pending row.
        # Both dialect predicates are required: sqlite_where is what create_all
        # builds in the unit-test database (see notification dedupe index).
        Index(
            "ux_sso_prov_pending_email",
            "tenant_id",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
        # One open request per Azure OID globally (OID is directory-unique).
        Index(
            "ux_sso_prov_pending_oid",
            "azure_oid",
            unique=True,
            postgresql_where=text("status = 'pending' AND azure_oid IS NOT NULL"),
            sqlite_where=text("status = 'pending' AND azure_oid IS NOT NULL"),
        ),
        Index(
            "ix_sso_prov_tenant_status",
            "tenant_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    azure_oid: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Opaque token shown to the requester; not a capability (no accept-by-token path).
    reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)

    status: Mapped[SSOProvisioningStatus] = mapped_column(
        CaseInsensitiveEnum(SSOProvisioningStatus, length=20),
        nullable=False,
        default=SSOProvisioningStatus.PENDING,
        server_default=text("'pending'"),
    )
    match_basis: Mapped[SSOProvisioningMatchBasis] = mapped_column(
        CaseInsensitiveEnum(SSOProvisioningMatchBasis, length=40),
        nullable=False,
    )

    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))

    # Naive UTC: asyncpg rejects aware values into TIMESTAMP WITHOUT TIME ZONE
    # (same reason AuditLogEntry uses NaiveUTCDateTime).
    first_attempt_at: Mapped[datetime] = mapped_column(NaiveUTCDateTime(), nullable=False)
    last_attempt_at: Mapped[datetime] = mapped_column(NaiveUTCDateTime(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(NaiveUTCDateTime(), nullable=False)
    decided_at: Mapped[Optional[datetime]] = mapped_column(NaiveUTCDateTime(), nullable=True)

    decided_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<SSOProvisioningRequest(id={self.id}, ref={self.reference!r}, "
            f"status={self.status!r}, tenant_id={self.tenant_id})>"
        )
