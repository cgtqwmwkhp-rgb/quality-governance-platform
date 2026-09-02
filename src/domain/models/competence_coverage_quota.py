"""Location coverage quotas — n of m appointed people (CB-PR5).

A quota is a duty on a *location*, not a row about a named person: "this site
must maintain at least two appointed first aiders". ADR-0020 stays — no
per-person compliance-schedule row is ever created from this table.

``match_department`` is the Atlas department string an operator explicitly
declares as counting toward this location. Atlas has no Location foreign key,
so the join is configured by hand; nothing here guesses a department from
``locations.name``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base

ROLE_FIRST_AIDER = "first_aider"
ROLE_FIRE_MARSHAL = "fire_marshal"
ROLE_MHFA = "mhfa"

#: The only roles a quota may be written for. Mirrored by a CHECK constraint so
#: a direct SQL insert cannot introduce a fourth role the counter cannot count.
COVERAGE_ROLE_KEYS: tuple[str, ...] = (ROLE_FIRST_AIDER, ROLE_FIRE_MARSHAL, ROLE_MHFA)

_ROLE_CHECK = "role_key IN ('first_aider', 'fire_marshal', 'mhfa')"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CompetenceCoverageQuota(Base):
    """One (location × role) coverage duty: ``required_n`` appointed people."""

    __tablename__ = "competence_coverage_quotas"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "location_id",
            "role_key",
            name="uq_competence_coverage_quotas_location_role",
        ),
        CheckConstraint("required_n >= 1", name="ck_competence_coverage_quotas_required_n"),
        CheckConstraint(_ROLE_CHECK, name="ck_competence_coverage_quotas_role_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_key: Mapped[str] = mapped_column(String(40), nullable=False)
    required_n: Mapped[int] = mapped_column(Integer, nullable=False)
    # Catalogue template_key of the location obligation this quota informs. The
    # schedule row is created separately from the catalogue; a quota never
    # creates one.
    template_key: Mapped[str] = mapped_column(String(80), nullable=False)
    match_department: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now, onupdate=_now)
