"""Explicit assessment template → PAMS characteristic bind (CB-PR4).

A QGP asset type called "Compressor" is not the PAMS characteristic
"Compressor". Nothing here joins by name: a bind row is created by hand,
one template to one characteristic, and deleting the row reverts the
overlay for that pair.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CompetenceAssessmentBind(Base):
    """One audit template ↔ one PAMS characteristic, per tenant."""

    __tablename__ = "competence_assessment_binds"
    __table_args__ = (
        UniqueConstraint("tenant_id", "template_id", name="uq_competence_assessment_binds_template"),
        UniqueConstraint("tenant_id", "characteristic_key", name="uq_competence_assessment_binds_characteristic"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("audit_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    characteristic_key: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
