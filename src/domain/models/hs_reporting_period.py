"""Reporting-period inputs used by the H&S performance board."""

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, TimestampMixin


class HsReportingPeriod(Base, TimestampMixin):
    """Tenant-scoped FTE and annual-hours assumptions for an H&S reporting year."""

    __tablename__ = "hs_reporting_periods"
    __table_args__ = (UniqueConstraint("tenant_id", "reporting_year", name="uq_hs_period_tenant_year"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    reporting_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    average_fte: Mapped[float] = mapped_column(Float, nullable=False)
    hours_per_fte_year: Mapped[float] = mapped_column(Float, nullable=False, default=2124)
    # When set by Admin, this is the authoritative hours figure for LTIFR/AFR.
    # When null, hours are derived from FTE × hours_per_fte_year × period pro-rata.
    manual_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
