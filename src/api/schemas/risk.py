"""Pydantic schemas for Risk Register API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ============== Risk Control Schemas ==============


class RiskControlBase(BaseModel):
    """Base schema for Risk Control."""

    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    control_type: str = Field(default="preventive", pattern="^(preventive|detective|corrective|directive)$")
    implementation_status: str = Field(
        default="planned",
        pattern="^(planned|in_progress|implemented|not_implemented|not_applicable)$",
    )
    effectiveness: Optional[str] = Field(None, pattern="^(effective|partially_effective|ineffective|not_tested)$")
    owner_id: Optional[int] = None

    # Standard mapping
    clause_ids: Optional[List[int]] = None
    control_ids: Optional[List[int]] = None

    # Testing
    last_tested_date: Optional[datetime] = None
    next_test_date: Optional[datetime] = None
    test_frequency_months: Optional[int] = None


class RiskControlCreate(RiskControlBase):
    """Schema for creating a Risk Control."""

    pass


class RiskControlUpdate(BaseModel):
    """Schema for updating a Risk Control."""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    control_type: Optional[str] = None
    implementation_status: Optional[str] = None
    effectiveness: Optional[str] = None
    owner_id: Optional[int] = None
    clause_ids: Optional[List[int]] = None
    control_ids: Optional[List[int]] = None
    last_tested_date: Optional[datetime] = None
    next_test_date: Optional[datetime] = None
    test_frequency_months: Optional[int] = None
    is_active: Optional[bool] = None


class RiskControlResponse(BaseModel):
    """Response schema for Risk Control.

    Decoupled from RiskControlBase to avoid inheriting input validators
    (min_length, max_length, pattern) that cause 500 errors on response serialization.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    risk_id: int
    title: str
    description: Optional[str] = None
    control_type: str = "preventive"
    implementation_status: str = "planned"
    effectiveness: Optional[str] = None
    owner_id: Optional[int] = None
    clause_ids: Optional[List[int]] = None
    control_ids: Optional[List[int]] = None
    last_tested_date: Optional[datetime] = None
    next_test_date: Optional[datetime] = None
    test_frequency_months: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ============== Risk Assessment Schemas ==============


class RiskAssessmentBase(BaseModel):
    """Base schema for Risk Assessment (point-in-time evaluation)."""

    assessment_date: datetime
    assessment_type: str = Field(default="periodic", pattern="^(initial|periodic|triggered|post_incident)$")

    # Inherent risk (before controls)
    inherent_likelihood: int = Field(..., ge=1, le=5)
    inherent_impact: int = Field(..., ge=1, le=5)

    # Residual risk (after controls)
    residual_likelihood: int = Field(..., ge=1, le=5)
    residual_impact: int = Field(..., ge=1, le=5)

    # Target risk (desired state)
    target_likelihood: Optional[int] = Field(None, ge=1, le=5)
    target_impact: Optional[int] = Field(None, ge=1, le=5)

    # Assessment details
    assessment_notes: Optional[str] = None
    control_effectiveness_notes: Optional[str] = None

    # Assessor
    assessed_by_id: Optional[int] = None


class RiskAssessmentCreate(RiskAssessmentBase):
    """Schema for creating a Risk Assessment."""

    pass


class RiskAssessmentResponse(BaseModel):
    """Response schema for Risk Assessment.

    Decoupled from RiskAssessmentBase to avoid inheriting input validators
    (ge, le, pattern) that cause 500 errors on response serialization.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    risk_id: int
    assessment_date: datetime
    assessment_type: str = "periodic"
    inherent_likelihood: int
    inherent_impact: int
    residual_likelihood: int
    residual_impact: int
    target_likelihood: Optional[int] = None
    target_impact: Optional[int] = None
    assessment_notes: Optional[str] = None
    control_effectiveness_notes: Optional[str] = None
    assessed_by_id: Optional[int] = None

    # Calculated scores
    inherent_score: int
    residual_score: int
    target_score: Optional[int] = None

    # Risk levels
    inherent_level: str
    residual_level: str
    target_level: Optional[str] = None

    created_at: datetime


# ============== Risk Schemas ==============


class RiskBase(BaseModel):
    """Base schema for Risk."""

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1)

    # Classification
    category: str = Field(
        default="operational",
        pattern="^(strategic|operational|financial|compliance|reputational|safety|environmental|information_security)$",
    )
    subcategory: Optional[str] = Field(None, max_length=100)

    # Risk details
    risk_source: Optional[str] = Field(None, max_length=500)
    risk_event: Optional[str] = Field(None, max_length=500)
    risk_consequence: Optional[str] = Field(None, max_length=500)

    # Current assessment (convenience fields)
    likelihood: int = Field(default=3, ge=1, le=5)
    impact: int = Field(default=3, ge=1, le=5)

    # Ownership
    owner_id: Optional[int] = None
    department: Optional[str] = Field(None, max_length=100)

    # Review cycle
    review_frequency_months: int = Field(default=12, ge=1, le=60)
    next_review_date: Optional[datetime] = None

    # Standard mapping
    clause_ids: Optional[List[int]] = None
    control_ids: Optional[List[int]] = None

    # Linkages
    linked_audit_ids: Optional[List[int]] = None
    linked_incident_ids: Optional[List[int]] = None
    linked_policy_ids: Optional[List[int]] = None

    # Treatment
    treatment_strategy: str = Field(default="mitigate", pattern="^(accept|mitigate|transfer|avoid|exploit)$")
    treatment_plan: Optional[str] = None
    treatment_due_date: Optional[datetime] = None


class RiskCreate(RiskBase):
    """Schema for creating a Risk."""

    pass


class RiskUpdate(BaseModel):
    """Schema for updating a Risk."""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    risk_source: Optional[str] = None
    risk_event: Optional[str] = None
    risk_consequence: Optional[str] = None
    likelihood: Optional[int] = Field(None, ge=1, le=5)
    impact: Optional[int] = Field(None, ge=1, le=5)
    owner_id: Optional[int] = None
    department: Optional[str] = None
    review_frequency_months: Optional[int] = Field(None, ge=1, le=60)
    next_review_date: Optional[datetime] = None
    clause_ids: Optional[List[int]] = None
    control_ids: Optional[List[int]] = None
    linked_audit_ids: Optional[List[int]] = None
    linked_incident_ids: Optional[List[int]] = None
    linked_policy_ids: Optional[List[int]] = None
    treatment_strategy: Optional[str] = None
    treatment_plan: Optional[str] = None
    treatment_due_date: Optional[datetime] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


class RiskResponse(BaseModel):
    """Response schema for Risk.

    Decoupled from RiskBase to avoid inheriting input validators
    (min_length, max_length, ge, le, pattern) that cause 500 errors on response serialization.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    reference_number: str
    title: str
    description: str

    # Classification
    category: str = "operational"
    subcategory: Optional[str] = None

    # Risk details
    risk_source: Optional[str] = None
    risk_event: Optional[str] = None
    risk_consequence: Optional[str] = None

    # Current assessment
    likelihood: int = 3
    impact: int = 3

    # Ownership
    owner_id: Optional[int] = None
    department: Optional[str] = None

    # Review cycle
    review_frequency_months: int = 12
    next_review_date: Optional[datetime] = None

    # Standard mapping — model columns are *_json_legacy after normalisation migration
    clause_ids: Optional[List[int]] = Field(None, validation_alias="clause_ids_json_legacy")
    control_ids: Optional[List[int]] = Field(None, validation_alias="control_ids_json_legacy")

    # Linkages — same legacy column names
    linked_audit_ids: Optional[List[int]] = Field(None, validation_alias="linked_audit_ids_json_legacy")
    linked_incident_ids: Optional[List[int]] = Field(None, validation_alias="linked_incident_ids_json_legacy")
    linked_policy_ids: Optional[List[int]] = Field(None, validation_alias="linked_policy_ids_json")

    # Treatment
    treatment_strategy: str = "mitigate"
    treatment_plan: Optional[str] = None
    treatment_due_date: Optional[datetime] = None

    # Calculated fields
    risk_score: int
    risk_level: str

    # Status
    status: str
    is_active: bool

    # Timestamps
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class RiskDetailResponse(RiskResponse):
    """Schema for detailed Risk response with controls and assessments."""

    controls: List[RiskControlResponse] = []
    assessments: List[RiskAssessmentResponse] = []
    control_count: int = 0
    open_action_count: int = 0


class RiskListResponse(BaseModel):
    """Schema for paginated risk list response."""

    items: List[RiskResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============== Risk Matrix Schemas ==============


class RiskMatrixCell(BaseModel):
    """Schema for a cell in the risk matrix."""

    likelihood: int
    impact: int
    score: int
    level: str
    color: str
    risk_count: int = 0


class RiskMatrixResponse(BaseModel):
    """Schema for risk matrix response."""

    matrix: List[List[RiskMatrixCell]]
    total_risks: int
    risks_by_level: dict


# ============== Risk Statistics Schemas ==============


class RiskStatistics(BaseModel):
    """Schema for risk statistics."""

    total_risks: int
    active_risks: int
    risks_by_category: dict
    risks_by_level: dict
    risks_requiring_review: int
    overdue_treatments: int
    average_risk_score: float
