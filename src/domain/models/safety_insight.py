"""Persisted Safety Insights Analyst runs, themes, and dimension rollups."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import AuditTrailMixin, Base, CaseInsensitiveEnum, TimestampMixin


class SafetyInsightRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SafetyInsightRun(Base, TimestampMixin, AuditTrailMixin):
    """One deep-analysis job over a filtered case corpus."""

    __tablename__ = "safety_insight_runs"
    __table_args__ = (
        Index("ix_safety_insight_runs_tenant_status", "tenant_id", "status"),
        Index("ix_safety_insight_runs_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    status: Mapped[SafetyInsightRunStatus] = mapped_column(
        CaseInsensitiveEnum(SafetyInsightRunStatus),
        default=SafetyInsightRunStatus.QUEUED,
        nullable=False,
        index=True,
    )
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Request filters
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="org")  # org | topic
    topic_query: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    modules_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    date_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    date_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    min_cluster_size: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    include_synthesis: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_benchmark: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Results / honesty
    models_used_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    corpus_summary_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ratios_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    quality_scorecard_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    synthesis_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    benchmarks_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    synthesis_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    research_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class SafetyInsightTheme(Base, TimestampMixin):
    """Micro-theme cluster produced by a deep-run."""

    __tablename__ = "safety_insight_themes"
    __table_args__ = (Index("ix_safety_insight_themes_run", "run_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("safety_insight_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    module_scope: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    share: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    velocity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # emerging|stable|declining
    severity_overlay: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SafetyInsightThemeCase(Base):
    """Validated case membership for a micro-theme (citation ground truth)."""

    __tablename__ = "safety_insight_theme_cases"
    __table_args__ = (
        Index("ix_safety_insight_theme_cases_theme", "theme_id"),
        Index("ix_safety_insight_theme_cases_case", "module", "case_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("safety_insight_themes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("safety_insight_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(30), nullable=False)  # incident|near_miss|rta|complaint
    case_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_number: Mapped[str] = mapped_column(String(50), nullable=False)


class SafetyInsightDimension(Base, TimestampMixin):
    """Deterministic repeat-dimension rollup (person/location/vehicle/asset/contract)."""

    __tablename__ = "safety_insight_dimensions"
    __table_args__ = (Index("ix_safety_insight_dimensions_run_type", "run_id", "dimension_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("safety_insight_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    dimension_type: Mapped[str] = mapped_column(String(30), nullable=False)
    dimension_key: Mapped[str] = mapped_column(String(300), nullable=False)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    case_refs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
