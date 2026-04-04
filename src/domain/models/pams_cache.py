"""PAMS Van Checklist cache tables (QGP PostgreSQL).

Celery sync task periodically copies rows from the external PAMS MySQL
database into these mirror tables so that:
  - Page loads are fast (local PostgreSQL, no cross-network hop)
  - PAMS downtime does not break the UI
  - We can JOIN checklist data with defects / actions
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

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
