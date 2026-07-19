"""Governance Library Wave W3 — review pack API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class OpenPackRequest(BaseModel):
    document_id: int = Field(..., ge=1)


class DispositionRequest(BaseModel):
    notes: Optional[str] = None


class FindingResponse(BaseModel):
    id: int
    pack_id: int
    provider: str
    external_id: Optional[str] = None
    title: str
    summary: Optional[str] = None
    source_url: Optional[str] = None
    disposition: str
    dispositioned_by_id: Optional[int] = None
    dispositioned_at: Optional[datetime] = None
    disposition_notes: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PackResponse(BaseModel):
    id: int
    tenant_id: int
    document_id: int
    status: str
    window_days: int
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    opened_at: datetime
    opened_by_id: Optional[int] = None
    closed_at: Optional[datetime] = None
    closed_by_id: Optional[int] = None
    internal_inputs: Optional[dict[str, Any]] = None
    findings: list[FindingResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PackListResponse(BaseModel):
    items: list[PackResponse]
    total: int


class HorizonScanResponse(BaseModel):
    pack_id: int
    findings_created: int
    findings: list[FindingResponse]


class HorizonDocumentRow(BaseModel):
    document_id: int
    title: Optional[str] = None
    review_date: str
    pel_doc_ref: Optional[str] = None


class HorizonsResponse(BaseModel):
    months: int
    as_of: str
    horizon_end: str
    counts: dict[str, int]
    overdue: list[HorizonDocumentRow]
    due: list[HorizonDocumentRow]
    upcoming: list[HorizonDocumentRow]


class DashboardSummaryResponse(BaseModel):
    """Small Library / HSEQ dashboard counts."""

    as_of: str
    statutory_documents: int
    overdue_reviews: int
    open_review_packs: int


class DependencyVersionRow(BaseModel):
    id: int
    version_number: str
    status: str
    published_at: Optional[str] = None
    change_notes: Optional[str] = None


class DependencyCurrentTip(BaseModel):
    version_number: str
    status: str
    published_at: Optional[str] = None


class DependencyMapResponse(BaseModel):
    pel_doc_ref: str
    document_id: int
    title: str
    current_tip: DependencyCurrentTip
    superseded_history: list[DependencyVersionRow]
