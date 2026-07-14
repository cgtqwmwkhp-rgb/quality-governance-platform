"""Competence gap closed-loop actions — Assessor → Workforce golden thread."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, CaseInsensitiveEnum, TimestampMixin


class CompetenceGapSourceType(str, enum.Enum):
    ASSESSOR_CASE = "assessor_case"
    EXTERNAL_AUDIT_FINDING = "external_audit_finding"
    COMPLIANCE_EVIDENCE_LINK = "compliance_evidence_link"


class CompetenceGapSignalType(str, enum.Enum):
    COMPETENCE_GAP = "competence_gap"
    NONCONFORMITY = "nonconformity"


class CompetenceGapStatus(str, enum.Enum):
    OPEN = "open"
    LINKED = "linked"
    CAPA_CREATED = "capa_created"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class CompetenceGapAction(Base, TimestampMixin):
    """Tracks Assessor / evidence competence signals through CAPA and resolve."""

    __tablename__ = "competence_gap_actions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source_type",
            "source_id",
            name="uq_competence_gap_tenant_source",
        ),
        CheckConstraint(
            "signal_type IN ('competence_gap', 'nonconformity')",
            name="ck_competence_gap_signal_type",
        ),
        CheckConstraint(
            "status IN ('open', 'linked', 'capa_created', 'resolved', 'dismissed')",
            name="ck_competence_gap_status",
        ),
        Index("ix_competence_gap_tenant_status", "tenant_id", "status"),
        Index("ix_competence_gap_engineer", "engineer_id"),
        Index("ix_competence_gap_capa", "capa_action_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    signal_type: Mapped[CompetenceGapSignalType] = mapped_column(
        CaseInsensitiveEnum(CompetenceGapSignalType),
        nullable=False,
    )

    engineer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("engineers.id", ondelete="SET NULL"), nullable=True
    )
    # Prefer requirement_id while TrainingTicket spine lands on P0.
    requirement_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("competency_requirements.id", ondelete="SET NULL"), nullable=True
    )
    ticket_scheme: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    capa_action_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("capa_actions.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[CompetenceGapStatus] = mapped_column(
        CaseInsensitiveEnum(CompetenceGapStatus),
        default=CompetenceGapStatus.OPEN,
        nullable=False,
    )
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<CompetenceGapAction(id={self.id}, status={self.status}, source={self.source_type}:{self.source_id})>"
