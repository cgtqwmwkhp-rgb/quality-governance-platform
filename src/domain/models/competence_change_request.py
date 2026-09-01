"""Competence board change requests (CB-PR2).

QGP never writes PAMS or Citation. A row is the request; email is best-effort.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CompetenceChangeRequest(Base):
    """One open request per tenant × family × engineer × characteristic cell."""

    __tablename__ = "competence_change_requests"
    __table_args__ = (
        Index(
            "uq_competence_change_requests_open_cell",
            "tenant_id",
            "family",
            "engineer_id",
            "characteristic_key",
            unique=True,
            postgresql_where=text("status = 'open'"),
            sqlite_where=text("status = 'open'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    family: Mapped[str] = mapped_column(String(16), nullable=False)
    engineer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    characteristic_key: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    routed_to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    close_reason: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
