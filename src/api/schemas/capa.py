"""Pydantic schemas for CAPA (Corrective and Preventive Action) responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from src.domain.models.capa import CAPAPriority, CAPASource, CAPAStatus, CAPAType


class CAPAResponse(BaseModel):
    """Schema for single CAPA response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str
    title: str
    description: Optional[str] = None
    capa_type: CAPAType
    status: CAPAStatus
    priority: CAPAPriority
    source_type: Optional[CAPASource] = None
    source_id: Optional[int] = None
    root_cause: Optional[str] = None
    proposed_action: Optional[str] = None
    verification_method: Optional[str] = None
    verification_result: Optional[str] = None
    effectiveness_criteria: Optional[str] = None
    assigned_to_id: Optional[int] = None
    verified_by_id: Optional[int] = None
    created_by_id: int
    tenant_id: Optional[int] = None
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    iso_standard: Optional[str] = None
    clause_reference: Optional[str] = None


class CAPAListResponse(BaseModel):
    """Schema for paginated CAPA list response."""

    items: List[CAPAResponse]
    total: int
    page: int
    page_size: int
    pages: int


class CAPAStatsResponse(BaseModel):
    """Schema for CAPA statistics response."""

    total: int
    open: int
    in_progress: int
    overdue: int
