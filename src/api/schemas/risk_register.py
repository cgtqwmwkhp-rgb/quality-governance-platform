"""Enterprise Risk Register API response schemas."""

from typing import Any, Optional

from pydantic import BaseModel

# ============================================================================
# Risk List / CRUD Schemas
# ============================================================================


class RiskListItem(BaseModel):
    id: int
    reference: Optional[str] = None
    title: str
    category: Optional[str] = None
    department: Optional[str] = None
    inherent_score: Optional[int] = None
    residual_score: Optional[int] = None
    risk_level: str
    risk_color: str
    treatment_strategy: Optional[str] = None
    status: Optional[str] = None
    is_within_appetite: Optional[bool] = None
    risk_owner_name: Optional[str] = None
    next_review_date: Optional[str] = None


class RiskListResponse(BaseModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    pages: int = 1
    risks: list[RiskListItem] = []


class RiskCreatedResponse(BaseModel):
    id: int
    reference: Optional[str] = None
    message: str


class RiskUpdatedResponse(BaseModel):
    message: str
    id: int


class RiskAssessmentResponse(BaseModel):
    message: str
    inherent_score: Optional[int] = None
    residual_score: Optional[int] = None
    risk_level: Optional[str] = None
    is_within_appetite: Optional[bool] = None


# ============================================================================
# Risk Detail Schema
# ============================================================================


class ControlSummary(BaseModel):
    id: int
    reference: Optional[str] = None
    name: str
    control_type: Optional[str] = None
    effectiveness: Optional[str] = None


class KRISummary(BaseModel):
    id: int
    name: str
    current_value: Optional[float] = None
    current_status: Optional[str] = None
    last_updated: Optional[str] = None


class AssessmentHistoryItem(BaseModel):
    date: Optional[str] = None
    inherent_score: Optional[int] = None
    residual_score: Optional[int] = None
    status: Optional[str] = None


class RiskDetailResponse(BaseModel):
    id: int
    reference: Optional[str] = None
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    process: Optional[str] = None
    inherent_likelihood: Optional[int] = None
    inherent_impact: Optional[int] = None
    inherent_score: Optional[int] = None
    residual_likelihood: Optional[int] = None
    residual_impact: Optional[int] = None
    residual_score: Optional[int] = None
    target_score: Optional[int] = None
    risk_level: Optional[str] = None
    risk_color: Optional[str] = None
    risk_appetite: Optional[str] = None
    appetite_threshold: Optional[int] = None
    is_within_appetite: Optional[bool] = None
    treatment_strategy: Optional[str] = None
    treatment_plan: Optional[str] = None
    treatment_status: Optional[str] = None
    status: Optional[str] = None
    risk_owner_id: Optional[int] = None
    risk_owner_name: Optional[str] = None
    review_frequency_days: Optional[int] = None
    last_review_date: Optional[str] = None
    next_review_date: Optional[str] = None
    review_notes: Optional[str] = None
    is_escalated: Optional[bool] = None
    escalation_reason: Optional[str] = None
    identified_date: Optional[str] = None
    controls: list[ControlSummary] = []
    kris: list[KRISummary] = []
    assessment_history: list[AssessmentHistoryItem] = []


# ============================================================================
# Heat Map & Matrix Schemas
# ============================================================================


class RiskLevelConfig(BaseModel):
    color: str
    max_score: int


class RiskMatrixConfigResponse(BaseModel):
    matrix: list[list[Any]] = []
    likelihood_labels: list[str] = []
    likelihood_descriptions: list[str] = []
    impact_labels: list[str] = []
    impact_descriptions: list[str] = []
    levels: dict[str, RiskLevelConfig] = {}


# ============================================================================
# Bow-Tie Schemas
# ============================================================================


class BowTieElementCreatedResponse(BaseModel):
    id: int
    message: str


# ============================================================================
# KRI Schemas
# ============================================================================


class KRICreatedResponse(BaseModel):
    id: int
    message: str


class KRIValueUpdatedResponse(BaseModel):
    message: str
    current_value: Optional[float] = None
    current_status: Optional[str] = None


# ============================================================================
# Control Schemas
# ============================================================================


class ControlListItem(BaseModel):
    id: int
    reference: Optional[str] = None
    name: str
    description: Optional[str] = None
    control_type: Optional[str] = None
    control_nature: Optional[str] = None
    effectiveness: Optional[str] = None
    control_owner_name: Optional[str] = None
    implementation_status: Optional[str] = None


class ControlCreatedResponse(BaseModel):
    id: int
    reference: str
    message: str


class ControlLinkedResponse(BaseModel):
    message: str


# ============================================================================
# Appetite Schemas
# ============================================================================


class AppetiteStatementItem(BaseModel):
    id: int
    category: Optional[str] = None
    appetite_level: Optional[str] = None
    max_inherent_score: Optional[int] = None
    max_residual_score: Optional[int] = None
    escalation_threshold: Optional[int] = None
    statement: Optional[str] = None
    approved_by: Optional[str] = None
    approved_date: Optional[str] = None


# ============================================================================
# Summary Schemas
# ============================================================================


class RiskByLevel(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class RiskSummaryResponse(BaseModel):
    total_risks: int = 0
    by_level: RiskByLevel = RiskByLevel()
    outside_appetite: int = 0
    overdue_review: int = 0
    escalated: int = 0
    by_category: dict[str, int] = {}
