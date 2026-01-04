"""Root Cause Analysis (RTA) models."""

import enum
from typing import Optional

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, ReferenceNumberMixin, TimestampMixin
from src.infrastructure.database import Base

if False:
    from src.domain.models.incident import Incident


class RCAStatus(str, enum.Enum):
    """Status of Root Cause Analysis."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"


class RootCauseAnalysis(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Root Cause Analysis (RTA) model."""

    __tablename__ = "root_cause_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)

    # RTA details
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrective_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[RCAStatus] = mapped_column(SQLEnum(RCAStatus, name="rcastatus"), default=RCAStatus.DRAFT)

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="rtas")

    def __repr__(self) -> str:
        return f"<RootCauseAnalysis(id={self.id}, ref='{self.reference_number}', status='{self.status}')>"
