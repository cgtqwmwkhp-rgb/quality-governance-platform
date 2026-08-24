"""Schemas for the case closure-validation endpoints.

Shared by incidents, complaints, near misses and RTAs so the Close summary
dialog has one contract to read regardless of which register it is showing.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class CaseClosureBlockingItem(BaseModel):
    """An action or CAPA that is blocking case closure."""

    kind: str
    id: int
    reference_number: str
    title: str
    status: str
    action_key: str
    unblock_hint: str = "Complete or cancel this action before closing the case."


class CaseClosureLinkedInvestigation(BaseModel):
    """Linked investigation shown for context; it never blocks closure."""

    id: int
    reference_number: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None


class CaseClosureSummary(BaseModel):
    """Everything the Close summary dialog renders about the case."""

    case_type: str
    case_label: str
    id: int
    reference_number: Optional[str] = None
    title: Optional[str] = None
    status: str
    target_status: str
    severity: Optional[str] = None
    category: Optional[str] = None
    occurred_at: Optional[str] = None
    reported_at: Optional[str] = None
    created_at: Optional[str] = None
    closed_at: Optional[str] = None
    lessons_learnt: Optional[str] = None
    lessons_present: bool = False
    actions_total: int = 0
    actions_complete: int = 0
    actions_incomplete: int = 0
    linked_investigation: Optional[CaseClosureLinkedInvestigation] = None


class CaseClosureValidationResponse(BaseModel):
    """Closure-readiness result for a single case."""

    can_close: bool
    reasons: List[str] = Field(default_factory=list)
    open_work: List[CaseClosureBlockingItem] = Field(default_factory=list)
    open_work_count: int = 0
    lessons_present: bool = False
    transition_allowed: bool = Field(
        default=True,
        description="False when this status cannot move straight to closed, whatever else is in order.",
    )
    allowed_next_statuses: List[str] = Field(
        default_factory=list,
        description="Legal next statuses for this case, reported when the close transition is refused.",
    )
    summary: CaseClosureSummary

    model_config = {"json_schema_extra": {"examples": [{"can_close": False, "reasons": ["MISSING_LESSONS_LEARNT"]}]}}
