"""Unified external audit record — cross-scheme audit registry.

Stores audit-level summary data for every imported external audit regardless
of scheme (Achilles/UVDB, ISO, Planet Mark, Customer, etc.).  Provides a
single queryable table for dashboards, trend analysis, and filtering.
"""

from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base


class ExternalAuditRecord(Base):
    __tablename__ = "external_audit_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    scheme = Column(String(50), nullable=False, index=True)
    scheme_version = Column(String(50), nullable=True)
    scheme_label = Column(String(200), nullable=True)
    audit_run_id = Column(Integer, ForeignKey("audit_runs.id"), nullable=True, index=True)
    import_job_id = Column(Integer, ForeignKey("external_audit_import_jobs.id"), nullable=True, index=True)
    issuer_name = Column(String(200), nullable=True)
    company_name = Column(String(200), nullable=True)
    report_date = Column(DateTime, nullable=True)
    overall_score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)
    score_percentage = Column(Float, nullable=True)
    section_scores = Column(JSON, nullable=True)
    outcome_status = Column(String(50), nullable=True)
    findings_count = Column(Integer, nullable=True, default=0)
    major_findings = Column(Integer, nullable=True, default=0)
    minor_findings = Column(Integer, nullable=True, default=0)
    observations = Column(Integer, nullable=True, default=0)
    analysis_summary = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="completed")
