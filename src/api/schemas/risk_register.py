"""Enterprise Risk Register API response schemas."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

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
    trend: Optional[Literal["increasing", "stable", "decreasing"]] = None
    last_review_date: Optional[str] = None
    next_review_date: Optional[str] = None


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


class RiskProfileResponse(BaseModel):
    """Typed Excel Risk Card / profile shell payload (RR-P0)."""

    id: int
    reference: Optional[str] = None
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    treatment: Optional[str] = None
    inherent_likelihood: Optional[int] = None
    inherent_impact: Optional[int] = None
    inherent_score: Optional[int] = None
    inherent_level: Optional[str] = None
    residual_likelihood: Optional[int] = None
    residual_impact: Optional[int] = None
    residual_score: Optional[int] = None
    residual_level: Optional[str] = None
    trend: Optional[Literal["increasing", "stable", "decreasing"]] = None
    risk_owner_id: Optional[int] = None
    risk_owner_name: Optional[str] = None
    last_review_date: Optional[str] = None
    next_review_date: Optional[str] = None
    updated_at: Optional[str] = None
    created_at: Optional[str] = None
    assessment_history: list[AssessmentHistoryItem] = []
    linked_actions: list[Any] = []
    review_notes: Optional[str] = None


# ============================================================================
# Risk Notes & Activity (RR-W2)
# ============================================================================


class RiskNoteCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=16000)

    @model_validator(mode="before")
    @classmethod
    def strip_body(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("body"), str):
            return {**data, "body": data["body"].strip()}
        return data


class RiskNoteItem(BaseModel):
    id: int
    risk_id: int
    body: str
    created_by_id: int
    created_by_email: Optional[str] = None
    created_at: Optional[str] = None


class RiskNoteListResponse(BaseModel):
    items: list[RiskNoteItem] = []
    total: int = 0
    page: int = 1
    page_size: int = 50
    pages: int = 1


class RiskActivityEventItem(BaseModel):
    id: int
    risk_id: int
    event_type: str
    summary: str
    payload: Optional[dict[str, Any]] = None
    actor_id: int
    actor_email: Optional[str] = None
    created_at: Optional[str] = None


class RiskActivityListResponse(BaseModel):
    items: list[RiskActivityEventItem] = []
    total: int = 0
    page: int = 1
    page_size: int = 50
    pages: int = 1


# ============================================================================
# Risk Actions (CAPA SSOT) + Upstream 360 (RR-W3)
# ============================================================================


class RiskActionCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=16000)
    priority: Optional[str] = Field(default="medium")
    due_date: Optional[str] = Field(None, description="ISO date YYYY-MM-DD")
    assigned_to_id: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def strip_text(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        for key in ("title", "description"):
            if isinstance(out.get(key), str):
                out[key] = out[key].strip()
        return out


class RiskActionItem(BaseModel):
    id: int
    reference_number: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    source_type: str = "risk"
    source_id: int
    due_date: Optional[str] = None
    assigned_to_id: Optional[int] = None
    created_at: Optional[str] = None
    href: Optional[str] = None


class RiskActionListResponse(BaseModel):
    items: list[RiskActionItem] = []
    total: int = 0
    page: int = 1
    page_size: int = 50
    pages: int = 1


class RiskUpstreamItem(BaseModel):
    source_type: str
    source_id: int
    title: Optional[str] = None
    reference: Optional[str] = None
    href: str
    audit_run_id: Optional[int] = None


class RiskUpstreamResponse(BaseModel):
    items: list[RiskUpstreamItem] = []
    total: int = 0


class RiskOwnerUpdate(BaseModel):
    risk_owner_id: Optional[int] = None
    risk_owner_name: Optional[str] = Field(None, max_length=255)


class RiskOwnerResponse(BaseModel):
    id: int
    risk_owner_id: Optional[int] = None
    risk_owner_name: Optional[str] = None
    message: str = "Owner updated"


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


# ============================================================================
# Heat Map Response
# ============================================================================


class HeatMapCell(BaseModel):
    likelihood: int
    impact: int
    score: int
    level: str
    color: str
    risk_count: int = 0
    risk_ids: list[int] = []
    risk_ids_truncated: bool = False
    risk_titles: list[str] = []
    owners_sample: list[str] = []
    overdue_count: int = 0
    outside_appetite_count: int = 0
    intensity: float = 0.0
    above_appetite_band: bool = False
    movers: list[dict[str, Any]] = []


class HeatMapSummary(BaseModel):
    total_risks: int = 0
    critical_risks: int = 0
    high_risks: int = 0
    medium_risks: int = 0
    low_risks: int = 0
    outside_appetite: int = 0
    average_inherent_score: float = 0.0
    average_residual_score: float = 0.0


class HeatMapResponse(BaseModel):
    matrix: list[list[HeatMapCell]] = []
    cells: list[dict[str, Any]] = []
    summary: HeatMapSummary = HeatMapSummary()
    likelihood_labels: dict[int, str] = {}
    impact_labels: dict[int, str] = {}
    score_type: str = "residual"
    view_mode: str = "residual"
    filters_applied: Optional[dict[str, Any]] = None
    appetite_overlay: Optional[dict[str, Any]] = None

    class Config:
        extra = "allow"


# ============================================================================
# Bow-Tie Response
# ============================================================================


class BowTieResponse(BaseModel):
    risk: Optional[dict[str, Any]] = None
    causes: list[Any] = []
    prevention_barriers: list[Any] = []
    consequences: list[Any] = []
    mitigation_barriers: list[Any] = []
    escalation_factors: list[Any] = []
    controls: list[Any] = []

    class Config:
        extra = "allow"


# ============================================================================
# Enterprise KRI Dashboard Response
# ============================================================================


class EnterpriseKRIDashboardResponse(BaseModel):
    total_kris: int = 0
    red_count: int = 0
    amber_count: int = 0
    green_count: int = 0
    kris: list[dict[str, Any]] = []
