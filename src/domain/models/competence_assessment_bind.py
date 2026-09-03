"""Explicit assessment template → PAMS characteristic bind (CB-PR4 / CB-UI-2).

A QGP asset type called "Compressor" is not the PAMS characteristic
"Compressor". Nothing here joins by name: a bind row is created by hand,
one template to one characteristic, and deleting the row reverts the
overlay for that pair.

CB-UI-2 splits the pair by ``mode``. A field assessment and an induction are
two different demonstrations of the same characteristic, so both may be bound
to it — but only one published template each way, which is what the
``(tenant, characteristic, mode)`` unique constraint says. The reassessment
interval lives here rather than on the template because it is a property of
*this* bind: the same template bound as an induction need not expire on the
same clock as the field assessment.
"""

from __future__ import annotations

from datetime import datetime, timezone

from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base

FIELD_MODE = "field"
INDUCTION_MODE = "induction"
#: The two ways a characteristic can be demonstrated. Not an Enum column: the
#: LIVE table is a plain varchar and CB-PR4 rows predate the split.
BIND_MODES: tuple[str, ...] = (FIELD_MODE, INDUCTION_MODE)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CompetenceAssessmentBind(Base):
    """One published template ↔ one PAMS characteristic in one mode, per tenant."""

    __tablename__ = "competence_assessment_binds"
    __table_args__ = (
        UniqueConstraint("tenant_id", "template_id", name="uq_competence_assessment_binds_template"),
        UniqueConstraint(
            "tenant_id",
            "characteristic_key",
            "mode",
            name="uq_competence_assessment_binds_characteristic_mode",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("audit_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    characteristic_key: Mapped[str] = mapped_column(String(80), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default=FIELD_MODE)
    # Null means "no interval was declared on this bind" — the demonstration
    # then falls back to the CompetencyRequirement resolution CB-PR4 already
    # used. It is not "never expires" and must never be rendered as one.
    interval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
