"""Compliance Evidence Link model for mapping evidence to ISO clauses.

Persists the relationship between business entities (documents, audits,
incidents, policies, etc.) and ISO standard clauses. This is the core
data that drives compliance coverage, gap analysis, and audit reports.
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, CaseInsensitiveEnum, TimestampMixin


class EvidenceLinkMethod(str, enum.Enum):
    MANUAL = "manual"
    AUTO = "auto"
    AI = "ai"


class EvidenceLinkStatus(str, enum.Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class EvidenceScheme(str, enum.Enum):
    ISO9001 = "iso9001"
    ISO14001 = "iso14001"
    ISO45001 = "iso45001"
    ISO27001 = "iso27001"
    UVDB = "uvdb"
    PLANET_MARK = "planet_mark"
    CUSTOM = "custom"


class EvidenceSignalType(str, enum.Enum):
    """How an operational record relates to a standard clause.

    Documents are usually ``evidence`` of conformance. Incidents, RTAs,
    near misses, complaints, and audit findings are usually
    ``nonconformity`` / ``gap`` / ``opportunity`` signals — not proof of
    conformance. Mixing these up pollutes certification evidence packs.

    Coverage honesty: only ``evidence`` (and legacy null signal_type) counts
    toward IMS/compliance ``coverage_percentage``. NC / gap / opportunity
    links are retained for assessor workflows but must not inflate coverage.
    """

    EVIDENCE = "evidence"
    NONCONFORMITY = "nonconformity"
    GAP = "gap"
    OPPORTUNITY = "opportunity"


class ComplianceEvidenceLink(Base, TimestampMixin):
    """Maps a business entity to an ISO clause as evidence of compliance.

    entity_type + entity_id form a polymorphic reference to the source
    record (document, audit finding, incident, policy, action, etc.).
    clause_id references the in-memory ISO clause catalogue maintained
    by ISOComplianceService.
    """

    __tablename__ = "compliance_evidence_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)

    clause_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    linked_by: Mapped[EvidenceLinkMethod] = mapped_column(
        CaseInsensitiveEnum(EvidenceLinkMethod),
        nullable=False,
        default=EvidenceLinkMethod.MANUAL,
    )
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    status: Mapped[Optional[EvidenceLinkStatus]] = mapped_column(
        CaseInsensitiveEnum(EvidenceLinkStatus),
        nullable=True,
        default=EvidenceLinkStatus.PROPOSED,
    )
    scheme: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    auto_applied: Mapped[bool] = mapped_column(default=False, server_default="false")
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signal_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)

    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_by_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_cel_entity", "entity_type", "entity_id"),
        Index("ix_cel_clause", "clause_id"),
        Index("ix_cel_tenant_entity_clause", "tenant_id", "entity_type", "entity_id", "clause_id", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceEvidenceLink(id={self.id}, "
            f"entity='{self.entity_type}:{self.entity_id}', "
            f"clause='{self.clause_id}')>"
        )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def effective_status(self) -> EvidenceLinkStatus:
        """Backward-compat: legacy manual links without status are confirmed."""
        if self.status is not None:
            return self.status
        if self.linked_by == EvidenceLinkMethod.MANUAL:
            return EvidenceLinkStatus.CONFIRMED
        return EvidenceLinkStatus.PROPOSED
