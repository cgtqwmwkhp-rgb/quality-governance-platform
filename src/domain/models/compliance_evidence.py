"""Compliance Evidence Link model for mapping evidence to ISO clauses.

Persists the relationship between business entities (documents, audits,
incidents, policies, etc.) and ISO standard clauses. This is the core
data that drives compliance coverage, gap analysis, and audit reports.
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import TimestampMixin
from src.infrastructure.database import Base


class EvidenceLinkMethod(str, enum.Enum):
    MANUAL = "manual"
    AUTO = "auto"
    AI = "ai"


class ComplianceEvidenceLink(Base, TimestampMixin):
    """Maps a business entity to an ISO clause as evidence of compliance.

    entity_type + entity_id form a polymorphic reference to the source
    record (document, audit finding, incident, policy, action, etc.).
    clause_id references the in-memory ISO clause catalogue maintained
    by ISOComplianceService.
    """

    __tablename__ = "compliance_evidence_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)

    clause_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    linked_by: Mapped[EvidenceLinkMethod] = mapped_column(
        SQLEnum(EvidenceLinkMethod, native_enum=False),
        nullable=False,
        default=EvidenceLinkMethod.MANUAL,
    )
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

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
        Index("ix_cel_entity_clause", "entity_type", "entity_id", "clause_id", unique=True),
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
