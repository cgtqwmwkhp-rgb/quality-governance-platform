"""Assessment demonstration overlay on a PAMS characteristic (CB-PR4).

Separate from ``competency_records`` on purpose: that table is the workshop
asset-type contract and keeps ``asset_type_id`` NOT NULL. A demonstration is
keyed by PAMS characteristic instead, so an assessment can be shown over an
issued plant cell without inventing an asset type.

Issuance still lives in PAMS. A failed demonstration never deletes it — it
opens a change request for IT-Admin.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CompetenceDemonstration(Base):
    """One assessment run demonstrated against one bound characteristic."""

    __tablename__ = "competence_demonstrations"
    __table_args__ = (
        UniqueConstraint("source_run_id", name="uq_competence_demonstrations_source_run"),
        Index(
            "ix_competence_demonstrations_cell",
            "tenant_id",
            "engineer_id",
            "characteristic_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    engineer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    characteristic_key: Mapped[str] = mapped_column(String(80), nullable=False)
    template_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    assessed_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
