from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class FiveWhysAnalysisResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    status: str = "in_progress"
    iterations: list[dict[str, Any]] = []
    root_cause: Optional[str] = None
    
    class Config:
        from_attributes = True


class FishboneDiagramResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    status: str = "in_progress"
    causes: list[dict[str, Any]] = []
    root_cause: Optional[str] = None
    
    class Config:
        from_attributes = True


class RCACAPAResponse(BaseModel):
    id: int
    title: str
    status: str
    investigation_id: Optional[int] = None
    due_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============================================================================
# Five-Whys Response Schemas
# ============================================================================


class CreateFiveWhysResponse(BaseModel):
    id: int
    problem_statement: str
    whys: list[Any]
    created_at: datetime


class FiveWhysDetailResponse(BaseModel):
    id: int
    problem_statement: str
    whys: list[Any]
    root_causes: Any = None
    primary_root_cause: Optional[str] = None
    contributing_factors: Optional[list[str]] = None
    proposed_actions: Optional[list[Any]] = None
    completed: bool
    completed_at: Optional[datetime] = None
    why_chain: list[Any] = []


class AddWhyIterationResponse(BaseModel):
    id: int
    whys: list[Any]
    why_count: int


class SetFiveWhysRootCauseResponse(BaseModel):
    id: int
    primary_root_cause: str
    root_causes: Any = None


class CompleteFiveWhysResponse(BaseModel):
    id: int
    completed: bool
    completed_at: Optional[datetime] = None


class FiveWhysSummaryItem(BaseModel):
    id: int
    problem_statement: str
    completed: bool
    created_at: datetime


class EntityFiveWhysListResponse(BaseModel):
    entity_type: str
    entity_id: int
    analyses: list[FiveWhysSummaryItem] = []


# ============================================================================
# Fishbone Response Schemas
# ============================================================================


class CreateFishboneResponse(BaseModel):
    id: int
    effect_statement: str
    causes: Any = None
    created_at: datetime


class FishboneDetailResponse(BaseModel):
    id: int
    effect_statement: str
    causes: Any = None
    primary_causes: Optional[list[str]] = None
    root_cause: Optional[str] = None
    root_cause_category: Optional[str] = None
    proposed_actions: Optional[list[Any]] = None
    completed: bool
    cause_counts: Any = None


class AddFishboneCauseResponse(BaseModel):
    id: int
    causes: Any = None
    cause_counts: Any = None


class SetFishboneRootCauseResponse(BaseModel):
    id: int
    root_cause: str
    root_cause_category: str


class CompleteFishboneResponse(BaseModel):
    id: int
    completed: bool
    completed_at: Optional[datetime] = None


# ============================================================================
# CAPA Response Schemas
# ============================================================================


class CreateCAPAResponse(BaseModel):
    id: int
    action_type: str
    title: str
    status: str
    due_date: Optional[datetime] = None


class UpdateCAPAStatusResponse(BaseModel):
    id: int
    status: str
    completed_at: Optional[datetime] = None


class VerifyCAPAResponse(BaseModel):
    id: int
    status: str
    is_effective: bool
    verified_at: Optional[datetime] = None


class CAPASummaryItem(BaseModel):
    id: int
    action_type: str
    title: str
    status: str
    priority: str
    due_date: Optional[datetime] = None


class InvestigationCAPAListResponse(BaseModel):
    investigation_id: int
    capas: list[CAPASummaryItem] = []


class OverdueCAPASummaryItem(BaseModel):
    id: int
    title: str
    due_date: Optional[datetime] = None
    status: str
    priority: str


class OverdueCAPAListResponse(BaseModel):
    overdue_count: int
    capas: list[OverdueCAPASummaryItem] = []
