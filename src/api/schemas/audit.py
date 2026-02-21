"""Pydantic schemas for Audit & Inspection API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.schemas.validators import sanitize_field

# ============== Question Types & Options ==============


class QuestionOptionBase(BaseModel):
    """Base schema for question options (MCQ, dropdown, etc.)."""

    value: str = Field(..., min_length=1, max_length=200)
    label: str = Field(..., min_length=1, max_length=200)
    score: Optional[float] = None
    is_correct: Optional[bool] = None
    triggers_finding: bool = False
    finding_severity: Optional[str] = None


class ConditionalLogicRule(BaseModel):
    """Schema for conditional logic rules."""

    source_question_id: int
    operator: str = Field(
        ...,
        pattern="^(equals|not_equals|contains|greater_than|less_than|is_empty|is_not_empty)$",
    )
    value: Optional[Any] = None
    action: str = Field(..., pattern="^(show|hide|require|skip)$")


class EvidenceRequirement(BaseModel):
    """Schema for evidence requirements."""

    required: bool = False
    min_attachments: int = 0
    max_attachments: int = 10
    allowed_types: List[str] = Field(default_factory=lambda: ["image", "document", "video"])
    require_photo: bool = False
    require_signature: bool = False


# ============== Audit Question Schemas ==============


class AuditQuestionBase(BaseModel):
    """Base schema for Audit Question."""

    question_text: str = Field(..., min_length=1, max_length=1000)
    question_type: str = Field(
        ...,
        pattern="^(text|textarea|number|checkbox|radio|dropdown|date|datetime|signature|photo|file|rating|yes_no|pass_fail|score)$",
    )
    description: Optional[str] = Field(None, max_length=2000)
    help_text: Optional[str] = Field(None, max_length=500)

    # Question configuration
    is_required: bool = True
    allow_na: bool = False

    @field_validator("question_text", "description", "help_text", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)

    # Scoring
    max_score: Optional[float] = None
    weight: float = 1.0

    # Options for MCQ/dropdown/radio
    options: Optional[List[QuestionOptionBase]] = None

    # Numeric constraints
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    decimal_places: Optional[int] = None

    # Text constraints
    min_length: Optional[int] = None
    max_length: Optional[int] = None

    # Evidence requirements
    evidence_requirements: Optional[EvidenceRequirement] = None

    # Conditional logic
    conditional_logic: Optional[List[ConditionalLogicRule]] = None

    # Standard mapping
    clause_ids: Optional[List[int]] = None
    control_ids: Optional[List[int]] = None

    # Risk scoring
    risk_category: Optional[str] = None
    risk_weight: Optional[float] = None

    # Display
    sort_order: int = 0


class AuditQuestionCreate(AuditQuestionBase):
    """Schema for creating an Audit Question."""

    section_id: Optional[int] = None


class AuditQuestionUpdate(BaseModel):
    """Schema for updating an Audit Question."""

    question_text: Optional[str] = Field(None, min_length=1, max_length=1000)
    question_type: Optional[str] = Field(
        None,
        pattern="^(text|textarea|number|checkbox|radio|dropdown|date|datetime|signature|photo|file|rating|yes_no|pass_fail|score)$",
    )
    description: Optional[str] = None
    help_text: Optional[str] = None
    is_required: Optional[bool] = None
    allow_na: Optional[bool] = None
    max_score: Optional[float] = None
    weight: Optional[float] = None
    options: Optional[List[QuestionOptionBase]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    decimal_places: Optional[int] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    evidence_requirements: Optional[EvidenceRequirement] = None
    conditional_logic: Optional[List[ConditionalLogicRule]] = None
    clause_ids: Optional[List[int]] = None
    control_ids: Optional[List[int]] = None
    risk_category: Optional[str] = None
    risk_weight: Optional[float] = None
    section_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("question_text", "description", "help_text", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class AuditQuestionResponse(AuditQuestionBase):
    """Schema for Audit Question response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    section_id: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ============== Audit Section Schemas ==============


class AuditSectionBase(BaseModel):
    """Base schema for Audit Section."""

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    sort_order: int = 0
    weight: float = 1.0
    is_repeatable: bool = False
    max_repeats: Optional[int] = None

    @field_validator("title", "description", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class AuditSectionCreate(AuditSectionBase):
    """Schema for creating an Audit Section."""

    pass


class AuditSectionUpdate(BaseModel):
    """Schema for updating an Audit Section."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    weight: Optional[float] = None
    is_repeatable: Optional[bool] = None
    max_repeats: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("title", "description", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class AuditSectionResponse(AuditSectionBase):
    """Schema for Audit Section response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    questions: List[AuditQuestionResponse] = []


# ============== Audit Template Schemas ==============


class AuditTemplateBase(BaseModel):
    """Base schema for Audit Template."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=100)

    # Template configuration
    audit_type: str = Field(default="inspection", pattern="^(inspection|audit|assessment|checklist|survey)$")
    frequency: Optional[str] = Field(None, pattern="^(daily|weekly|monthly|quarterly|annually|ad_hoc)$")

    @field_validator("name", "description", "category", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)

    # Scoring configuration
    scoring_method: str = Field(default="percentage", pattern="^(percentage|points|weighted|pass_fail)$")
    passing_score: Optional[float] = None

    # Standard mapping
    standard_ids: Optional[List[int]] = None

    # Mobile configuration
    allow_offline: bool = False
    require_gps: bool = False
    require_signature: bool = False

    # Workflow
    require_approval: bool = False
    auto_create_findings: bool = True


class AuditTemplateCreate(AuditTemplateBase):
    """Schema for creating an Audit Template."""

    pass


class AuditTemplateUpdate(BaseModel):
    """Schema for updating an Audit Template."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    audit_type: Optional[str] = None
    frequency: Optional[str] = None
    scoring_method: Optional[str] = None
    passing_score: Optional[float] = None
    standard_ids: Optional[List[int]] = None
    allow_offline: Optional[bool] = None
    require_gps: Optional[bool] = None
    require_signature: Optional[bool] = None
    require_approval: Optional[bool] = None
    auto_create_findings: Optional[bool] = None
    is_active: Optional[bool] = None
    is_published: Optional[bool] = None

    @field_validator("name", "description", "category", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class AuditTemplateResponse(AuditTemplateBase):
    """Schema for Audit Template response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: Optional[str]
    version: int
    is_active: bool
    is_published: bool
    archived_at: Optional[datetime] = None
    archived_by_id: Optional[int] = None
    created_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class AuditTemplateDetailResponse(AuditTemplateResponse):
    """Schema for detailed Audit Template response with sections and questions."""

    sections: List[AuditSectionResponse] = []
    question_count: int = 0
    section_count: int = 0


class AuditTemplateListResponse(BaseModel):
    """Schema for paginated audit template list response."""

    items: List[AuditTemplateResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============== Audit Run Schemas ==============


class AuditRunBase(BaseModel):
    """Base schema for Audit Run."""

    title: Optional[str] = Field(None, max_length=300)
    location: Optional[str] = Field(None, max_length=200)
    location_details: Optional[str] = Field(None, max_length=500)
    scheduled_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None

    # GPS coordinates
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator("title", "location", "location_details", "notes", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class AuditRunCreate(AuditRunBase):
    """Schema for creating an Audit Run."""

    template_id: int
    assigned_to_id: Optional[int] = None


class AuditRunUpdate(BaseModel):
    """Schema for updating an Audit Run."""

    title: Optional[str] = Field(None, max_length=300)
    location: Optional[str] = None
    location_details: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    assigned_to_id: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = Field(
        None,
        pattern="^(draft|scheduled|in_progress|pending_review|cancelled)$",
    )

    @field_validator("title", "location", "location_details", "notes", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class AuditRunResponse(AuditRunBase):
    """Schema for Audit Run response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str
    template_id: int
    template_version: int
    status: str
    assigned_to_id: Optional[int]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    score: Optional[float]
    max_score: Optional[float]
    score_percentage: Optional[float]
    passed: Optional[bool]
    created_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class AuditRunDetailResponse(AuditRunResponse):
    """Schema for detailed Audit Run response with responses."""

    template_name: Optional[str] = None
    responses: List["AuditResponseResponse"] = []
    findings: List["AuditFindingResponse"] = []
    completion_percentage: float = 0.0


class AuditRunListResponse(BaseModel):
    """Schema for paginated audit run list response."""

    items: List[AuditRunResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============== Audit Response Schemas ==============


class AuditResponseBase(BaseModel):
    """Base schema for Audit Response (answer to a question)."""

    response_value: Optional[str] = None
    response_text: Optional[str] = None
    response_number: Optional[float] = None
    response_bool: Optional[bool] = None
    response_date: Optional[datetime] = None
    response_json: Optional[Dict[str, Any]] = None
    is_na: bool = False
    score: Optional[float] = None
    notes: Optional[str] = None

    @field_validator("response_value", "response_text", "notes", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class AuditResponseCreate(AuditResponseBase):
    """Schema for creating an Audit Response."""

    question_id: int
    max_score: Optional[float] = None


class AuditResponseUpdate(BaseModel):
    """Schema for updating an Audit Response."""

    response_value: Optional[str] = None
    response_text: Optional[str] = None
    response_number: Optional[float] = None
    response_bool: Optional[bool] = None
    response_date: Optional[datetime] = None
    response_json: Optional[Dict[str, Any]] = None
    is_na: Optional[bool] = None
    score: Optional[float] = None
    max_score: Optional[float] = None
    notes: Optional[str] = None

    @field_validator("response_value", "response_text", "notes", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class AuditResponseResponse(AuditResponseBase):
    """Schema for Audit Response response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    question_id: int
    max_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime


# ============== Audit Finding Schemas ==============


class AuditFindingBase(BaseModel):
    """Base schema for Audit Finding."""

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1)
    severity: str = Field(default="medium", pattern="^(critical|high|medium|low|observation)$")
    finding_type: str = Field(
        default="nonconformity",
        pattern="^(nonconformity|observation|opportunity|positive)$",
    )

    # Standard mapping
    clause_ids: Optional[List[int]] = None
    control_ids: Optional[List[int]] = None

    # Risk linkage
    risk_ids: Optional[List[int]] = None

    # Corrective action
    corrective_action_required: bool = True
    corrective_action_due_date: Optional[datetime] = None

    @field_validator("title", "description", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class AuditFindingCreate(AuditFindingBase):
    """Schema for creating an Audit Finding."""

    question_id: Optional[int] = None


class AuditFindingUpdate(BaseModel):
    """Schema for updating an Audit Finding."""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    severity: Optional[str] = Field(None, pattern="^(critical|high|medium|low|observation)$")
    finding_type: Optional[str] = Field(None, pattern="^(nonconformity|observation|opportunity|positive)$")
    clause_ids: Optional[List[int]] = None
    control_ids: Optional[List[int]] = None
    risk_ids: Optional[List[int]] = None
    corrective_action_required: Optional[bool] = None
    corrective_action_due_date: Optional[datetime] = None
    status: Optional[str] = Field(
        None,
        pattern="^(open|in_progress|pending_verification|closed|deferred)$",
    )

    @field_validator("title", "description", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class AuditFindingResponse(AuditFindingBase):
    """Schema for Audit Finding response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str
    run_id: int
    question_id: Optional[int]
    status: str
    created_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class AuditFindingListResponse(BaseModel):
    """Schema for paginated audit finding list response."""

    items: List[AuditFindingResponse]
    total: int
    page: int
    page_size: int
    pages: int


class PurgeExpiredTemplatesResponse(BaseModel):
    purged_count: int
    purged_templates: List[str]


class ArchiveTemplateResponse(BaseModel):
    message: str
    archived_at: str
    expires_at: str


# Forward references for nested models
AuditRunDetailResponse.model_rebuild()
