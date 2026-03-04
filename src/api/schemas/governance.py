"""Pydantic schemas for Governance API responses."""

from typing import Any, List, Optional

from pydantic import BaseModel


class GovernanceValidationResponse(BaseModel):
    """Response for supervisor validation."""

    valid: bool
    reason: Optional[str] = None


class GovernanceTemplateCheckResponse(BaseModel):
    """Response for template approval check."""

    approved: bool
    reason: Optional[str] = None


class GovernanceCompetencyGateRecord(BaseModel):
    """Single competency record in gate response."""

    id: int
    state: str


class GovernanceCompetencyGateResponse(BaseModel):
    """Response for competency gate check."""

    cleared: bool
    reason: Optional[str] = None
    records: List[GovernanceCompetencyGateRecord] = []
    active_count: Optional[int] = None


class GovernanceSchedulingSuggestion(BaseModel):
    """Single scheduling suggestion for upcoming assessments."""

    competency_record_id: int
    engineer_id: int
    asset_type_id: int
    template_id: int
    state: str
    expires_at: Optional[str] = None
    priority: str
    suggested_action: str
