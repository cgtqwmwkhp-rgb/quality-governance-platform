"""Response schemas for the audit reporting pack (``/audits/analytics/*``)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class AuditAnalyticsSummaryResponse(BaseModel):
    """Headline KPIs for the audit reporting pack."""

    period_days: int
    totals: int
    completed: int
    in_progress: int
    avg_score: float
    pass_rate: float
    essential_compliance_pct: float
    incomplete_critical_count: int


class AuditAnalyticsDimensionItem(BaseModel):
    """One row of a dimensional breakdown (e.g. one asset type, one week)."""

    key: str
    label: str
    run_count: int
    completed_count: int
    avg_score: float
    fail_rate: float
    essential_compliance_pct: Optional[float] = None


class AuditAnalyticsDimensionsResponse(BaseModel):
    """Dimensional breakdown response."""

    group_by: str
    period_days: int
    items: List[AuditAnalyticsDimensionItem]


class CriticalQueueItemResponse(BaseModel):
    """One incomplete/failed essential item in the critical queue."""

    model_config = ConfigDict(from_attributes=True)

    run_id: int
    run_reference_number: Optional[str] = None
    template_id: int
    template_name: Optional[str] = None
    question_id: int
    question_text: str
    reason: str
    finding_id: Optional[int] = None
    finding_status: Optional[str] = None


class CriticalQueueResponse(BaseModel):
    """Critical queue list response."""

    total: int
    items: List[CriticalQueueItemResponse]
