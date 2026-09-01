"""PAMS Van Checklist cache tables (QGP PostgreSQL).

Celery sync task periodically copies rows from the external PAMS MySQL
database into these mirror tables so that:
  - Page loads are fast (local PostgreSQL, no cross-network hop)
  - PAMS downtime does not break the UI
  - We can JOIN checklist data with defects / actions
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import Base


class PAMSVanChecklistCache(Base):
    """Mirror of PAMS vanchecklist table."""

    __tablename__ = "pams_van_checklist_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pams_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    def __repr__(self) -> str:
        return f"<PAMSVanChecklistCache(pams_id={self.pams_id})>"


class PAMSVanChecklistMonthlyCache(Base):
    """Mirror of PAMS vanchecklistmonthly table."""

    __tablename__ = "pams_van_checklist_monthly_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pams_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    def __repr__(self) -> str:
        return f"<PAMSVanChecklistMonthlyCache(pams_id={self.pams_id})>"


class PAMSSyncLog(Base):
    """Tracks each PAMS sync run for observability."""

    __tablename__ = "pams_sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(50), nullable=False)
    rows_synced: Mapped[int] = mapped_column(Integer, default=0)
    defects_detected: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<PAMSSyncLog(id={self.id}, table={self.table_name}, status={self.status})>"


class PamsCompetenceSnapshot(Base):
    """One PAMS competence view read. Board reads only the current snapshot."""

    __tablename__ = "pams_competence_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="loading")
    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rows: Mapped[list["PamsCompetenceRow"]] = relationship(
        "PamsCompetenceRow",
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )


class PamsCompetenceRow(Base):
    """One engineer × characteristic from a PAMS competence snapshot."""

    __tablename__ = "pams_competence_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("pams_competence_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pams_technician_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    engineer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    engineer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    depot: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    characteristic_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    thorough_exam: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    snapshot: Mapped["PamsCompetenceSnapshot"] = relationship("PamsCompetenceSnapshot", back_populates="rows")


class PamsCompetenceCurrent(Base):
    """Pointer to the live snapshot per tenant. Flip after rows are intact."""

    __tablename__ = "pams_competence_current"

    tenant_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("pams_competence_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
