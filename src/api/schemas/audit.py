"""Pydantic schemas for Audit & Inspection API."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

    model_config = ConfigDict(populate_by_name=True)

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

    # Scoring
    max_score: Optional[float] = None
    weight: float = 1.0

    # Options for MCQ/dropdown/radio
    options: Optional[List[QuestionOptionBase]] = Field(None, validation_alias="options_json")

    # Numeric constraints
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    decimal_places: Optional[int] = None

    # Text constraints
    min_length: Optional[int] = None
    max_length: Optional[int] = None

    # Evidence requirements
    evidence_requirements: Optional[EvidenceRequirement] = Field(None, validation_alias="evidence_requirements_json")

    # Conditional logic
    conditional_logic: Optional[List[ConditionalLogicRule]] = Field(None, validation_alias="conditional_logic_json")

    # Standard mapping
    clause_ids: Optional[List[int]] = Field(None, validation_alias="clause_ids_json")
    control_ids: Optional[List[int]] = Field(None, validation_alias="control_ids_json")

    # Risk scoring
    risk_category: Optional[str] = None
    risk_weight: Optional[float] = None

    # Workforce Development fields
    guidance: Optional[str] = None
    criticality: Optional[str] = Field(None, pattern="^(essential|good_to_have)$")
    regulatory_reference: Optional[str] = Field(None, max_length=200)
    guidance_notes: Optional[str] = None
    sign_off_required: bool = False
    assessor_guidance: Optional[Dict[str, Any]] = Field(None, validation_alias="assessor_guidance_json")
    training_materials: Optional[List[Any]] = Field(None, validation_alias="training_materials_json")
    failure_triggers_action: bool = False

    # Yes/No polarity: "yes" (default) or "no" — which answer is the positive/green one
    positive_answer: str = Field("yes", pattern="^(yes|no)$")

    # Display
    sort_order: int = 0


class AuditQuestionCreate(AuditQuestionBase):
    """Schema for creating an Audit Question."""

    section_id: Optional[int] = None


class AuditQuestionUpdate(BaseModel):
    """Schema for updating an Audit Question."""

    model_config = ConfigDict(populate_by_name=True)

    question_text: Optional[str] = Field(None, min_length=1, max_length=1000)
    question_type: Optional[str] = None
    description: Optional[str] = None
    help_text: Optional[str] = None
    is_required: Optional[bool] = None
    allow_na: Optional[bool] = None
    max_score: Optional[float] = None
    weight: Optional[float] = None
    options: Optional[List[QuestionOptionBase]] = Field(None, validation_alias="options_json")
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    evidence_requirements: Optional[EvidenceRequirement] = Field(None, validation_alias="evidence_requirements_json")
    conditional_logic: Optional[List[ConditionalLogicRule]] = Field(None, validation_alias="conditional_logic_json")
    clause_ids: Optional[List[int]] = Field(None, validation_alias="clause_ids_json")
    control_ids: Optional[List[int]] = Field(None, validation_alias="control_ids_json")
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    guidance: Optional[str] = None
    criticality: Optional[str] = None
    regulatory_reference: Optional[str] = None
    guidance_notes: Optional[str] = None
    sign_off_required: Optional[bool] = None
    assessor_guidance: Optional[Dict[str, Any]] = Field(None, validation_alias="assessor_guidance_json")
    training_materials: Optional[List[Any]] = Field(None, validation_alias="training_materials_json")
    failure_triggers_action: Optional[bool] = None
    positive_answer: Optional[str] = Field(None, pattern="^(yes|no)$")

    @field_validator("positive_answer")
    @classmethod
    def validate_positive_answer_not_null(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            raise ValueError("positive_answer cannot be null; use 'yes' or 'no'")
        return value


class AuditQuestionResponse(BaseModel):
    """Schema for Audit Question response.

    Does NOT inherit AuditQuestionBase so that input-only validators
    (pattern, min_length) don't re-run on output serialization.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    template_id: int
    section_id: Optional[int] = None
    question_text: str
    question_type: str
    description: Optional[str] = None
    help_text: Optional[str] = None
    is_required: bool = True
    allow_na: bool = False
    max_score: Optional[float] = None
    weight: float = 1.0
    options: Optional[List[Any]] = Field(None, validation_alias="options_json")
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    decimal_places: Optional[int] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    evidence_requirements: Optional[Dict[str, Any]] = Field(None, validation_alias="evidence_requirements_json")
    conditional_logic: Optional[List[Any]] = Field(None, validation_alias="conditional_logic_json")
    clause_ids: Optional[List[int]] = Field(None, validation_alias="clause_ids_json")
    control_ids: Optional[List[int]] = Field(None, validation_alias="control_ids_json")
    risk_category: Optional[str] = None
    risk_weight: Optional[float] = None
    guidance: Optional[str] = None
    criticality: Optional[str] = None
    regulatory_reference: Optional[str] = None
    guidance_notes: Optional[str] = None
    sign_off_required: bool = False
    assessor_guidance: Optional[Dict[str, Any]] = Field(None, validation_alias="assessor_guidance_json")
    training_materials: Optional[List[Any]] = Field(None, validation_alias="training_materials_json")
    failure_triggers_action: bool = False
    positive_answer: str = "yes"
    sort_order: int = 0
    is_active: bool = True
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


class AuditSectionResponse(BaseModel):
    """Schema for Audit Section response.

    Does NOT inherit AuditSectionBase so that input-only validators
    (min_length, max_length) don't re-run on output serialization.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    template_id: int
    title: str
    description: Optional[str] = None
    sort_order: int = 0
    weight: float = 1.0
    is_repeatable: bool = False
    max_repeats: Optional[int] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    questions: List[AuditQuestionResponse] = []


# ============== Audit Template Schemas ==============


class AuditTemplateBase(BaseModel):
    """Base schema for Audit Template."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=100)

    # Template configuration
    audit_type: str = Field(default="inspection", pattern="^(inspection|audit|assessment|checklist|survey)$")
    frequency: Optional[str] = Field(None, pattern="^(daily|weekly|monthly|quarterly|annually|ad_hoc)$")

    # Scoring configuration
    scoring_method: str = Field(default="percentage", pattern="^(percentage|points|weighted|equal|pass_fail)$")
    passing_score: Optional[float] = None

    # Standard mapping
    standard_ids: Optional[List[int]] = Field(None, validation_alias="standard_ids_json")

    # Mobile configuration
    allow_offline: bool = False
    require_gps: bool = False
    require_signature: bool = False

    # Workflow
    require_approval: bool = False
    auto_create_findings: bool = True

    # Workforce Development fields
    subcategory: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = Field(None, validation_alias="tags_json")
    estimated_duration: Optional[int] = Field(None, ge=1, description="Duration in minutes")
    pass_threshold: Optional[float] = Field(None, ge=0, le=100)


class AuditTemplateCreate(AuditTemplateBase):
    """Schema for creating an Audit Template."""

    pass


class AuditTemplateUpdate(BaseModel):
    """Schema for updating an Audit Template."""

    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    audit_type: Optional[str] = None
    frequency: Optional[str] = None
    scoring_method: Optional[str] = None
    passing_score: Optional[float] = None
    standard_ids: Optional[List[int]] = Field(None, validation_alias="standard_ids_json")
    allow_offline: Optional[bool] = None
    require_gps: Optional[bool] = None
    require_signature: Optional[bool] = None
    require_approval: Optional[bool] = None
    auto_create_findings: Optional[bool] = None
    is_active: Optional[bool] = None
    is_published: Optional[bool] = None
    subcategory: Optional[str] = None
    tags: Optional[List[str]] = Field(None, validation_alias="tags_json")
    estimated_duration: Optional[int] = None
    pass_threshold: Optional[float] = None
    template_status: Optional[str] = None
    expected_updated_at: Optional[str] = Field(
        None,
        description="ISO timestamp of the last known update; if provided, returns 409 on conflict",
    )


class AuditTemplateResponse(BaseModel):
    """Schema for Audit Template response.

    Does NOT inherit AuditTemplateBase so that input-only validators
    (pattern, min_length, ge, le) don't re-run on output serialization
    and cause 500s when legacy data doesn't match.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    external_id: str = ""
    reference_number: Optional[str] = None
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    audit_type: str = "inspection"
    frequency: Optional[str] = None
    scoring_method: str = "percentage"
    passing_score: Optional[float] = None
    standard_ids: Optional[List[int]] = Field(None, validation_alias="standard_ids_json")
    allow_offline: bool = False
    require_gps: bool = False
    require_signature: bool = False
    require_approval: bool = False
    auto_create_findings: bool = True
    subcategory: Optional[str] = None
    tags: Optional[List[str]] = Field(None, validation_alias="tags_json")
    estimated_duration: Optional[int] = None
    pass_threshold: Optional[float] = None
    version: int = 1
    is_active: bool = True
    is_published: bool = False
    template_status: str = "published"
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    question_count: int = 0
    section_count: int = 0


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


class ArchiveTemplateResponse(AuditTemplateResponse):
    """Schema for archived audit template response."""

    archived_at: Optional[datetime] = None


class PurgeExpiredTemplatesResponse(BaseModel):
    """Schema for purge expired templates response."""

    purged_count: int
    purged_templates: List[str] = []


# ============== Audit Run Schemas ==============

ALLOWED_AUDIT_SOURCE_ORIGINS = {"internal", "customer", "third_party", "certification"}
EXTERNAL_AUDIT_TYPE_TO_SOURCE_ORIGIN = {
    "customer": "customer",
    "iso": "certification",
    "planet_mark": "certification",
    "achilles_uvdb": "third_party",
    "other": "third_party",
}


class AuditRunBase(BaseModel):
    """Base schema for Audit Run."""

    title: Optional[str] = Field(None, max_length=300)
    location: Optional[str] = Field(None, max_length=200)
    location_details: Optional[str] = Field(None, max_length=500)
    scheduled_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    source_origin: Optional[str] = Field(None, max_length=50)
    assurance_scheme: Optional[str] = Field(None, max_length=100)
    external_body_name: Optional[str] = Field(None, max_length=255)
    external_auditor_name: Optional[str] = Field(None, max_length=255)
    external_reference: Optional[str] = Field(None, max_length=100)
    source_document_asset_id: Optional[int] = None
    source_document_label: Optional[str] = Field(None, max_length=255)

    # GPS coordinates
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator("source_origin")
    @classmethod
    def validate_source_origin(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if value not in ALLOWED_AUDIT_SOURCE_ORIGINS:
            raise ValueError(f"source_origin must be one of: {', '.join(sorted(ALLOWED_AUDIT_SOURCE_ORIGINS))}")
        return value


class AuditRunCreate(AuditRunBase):
    """Schema for creating an Audit Run."""

    template_id: int
    assigned_to_id: Optional[int] = None
    external_audit_type: Optional[Literal["customer", "iso", "planet_mark", "achilles_uvdb", "other"]] = None

    @model_validator(mode="after")
    def validate_external_import_fields(self) -> "AuditRunCreate":
        if self.external_audit_type is None:
            return self

        expected_source_origin = EXTERNAL_AUDIT_TYPE_TO_SOURCE_ORIGIN[self.external_audit_type]
        if self.source_origin and self.source_origin != expected_source_origin:
            raise ValueError(
                f"source_origin must be '{expected_source_origin}' when external_audit_type is "
                f"'{self.external_audit_type}'"
            )

        if self.external_audit_type == "iso" and not (self.assurance_scheme or "").strip():
            raise ValueError("assurance_scheme is required when external_audit_type is 'iso'")

        return self


class AuditRunUpdate(BaseModel):
    """Schema for updating an Audit Run."""

    title: Optional[str] = Field(None, max_length=300)
    location: Optional[str] = None
    location_details: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    assigned_to_id: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    source_origin: Optional[str] = Field(None, max_length=50)
    assurance_scheme: Optional[str] = Field(None, max_length=100)
    external_body_name: Optional[str] = Field(None, max_length=255)
    external_auditor_name: Optional[str] = Field(None, max_length=255)
    external_reference: Optional[str] = Field(None, max_length=100)
    source_document_asset_id: Optional[int] = None
    source_document_label: Optional[str] = Field(None, max_length=255)

    @field_validator("source_origin")
    @classmethod
    def validate_source_origin(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if value not in ALLOWED_AUDIT_SOURCE_ORIGINS:
            raise ValueError(f"source_origin must be one of: {', '.join(sorted(ALLOWED_AUDIT_SOURCE_ORIGINS))}")
        return value


class AuditRunResponse(BaseModel):
    """Schema for Audit Run response.

    Does NOT inherit AuditRunBase so that input-only validators
    (max_length) don't re-run on output serialization.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str
    template_id: int
    template_version: int
    title: Optional[str] = None
    location: Optional[str] = None
    location_details: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    source_origin: Optional[str] = None
    assurance_scheme: Optional[str] = None
    external_body_name: Optional[str] = None
    external_auditor_name: Optional[str] = None
    external_reference: Optional[str] = None
    source_document_asset_id: Optional[int] = None
    source_document_label: Optional[str] = None
    is_external_audit_import: bool = False
    is_external_import_intake: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str
    assigned_to_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    score: Optional[float] = None
    max_score: Optional[float] = None
    score_percentage: Optional[float] = None
    passed: Optional[bool] = None
    created_by_id: Optional[int] = None
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


class AuditResponseCreate(AuditResponseBase):
    """Schema for creating an Audit Response."""

    question_id: int


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
    notes: Optional[str] = None


class AuditResponseResponse(AuditResponseBase):
    """Schema for Audit Response response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    question_id: int
    created_at: datetime
    updated_at: datetime


# ============== Audit Finding Schemas ==============


class AuditFindingBase(BaseModel):
    """Base schema for Audit Finding."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1)
    severity: str = Field(default="medium", pattern="^(critical|high|medium|low|observation)$")
    finding_type: str = Field(
        default="nonconformity",
        pattern="^(nonconformity|observation|opportunity|positive)$",
    )

    # Standard mapping
    clause_ids: Optional[List[int]] = Field(None, validation_alias="clause_ids_json_legacy")
    control_ids: Optional[List[int]] = Field(None, validation_alias="control_ids_json")

    # Risk linkage
    risk_ids: Optional[List[int]] = Field(None, validation_alias="risk_ids_json")

    # Corrective action
    corrective_action_required: bool = True
    corrective_action_due_date: Optional[datetime] = None


class AuditFindingCreate(AuditFindingBase):
    """Schema for creating an Audit Finding."""

    question_id: Optional[int] = None


class AuditFindingUpdate(BaseModel):
    """Schema for updating an Audit Finding."""

    model_config = ConfigDict(populate_by_name=True)

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    severity: Optional[str] = None
    finding_type: Optional[str] = None
    clause_ids: Optional[List[int]] = Field(None, validation_alias="clause_ids_json_legacy")
    control_ids: Optional[List[int]] = Field(None, validation_alias="control_ids_json")
    risk_ids: Optional[List[int]] = Field(None, validation_alias="risk_ids_json")
    corrective_action_required: Optional[bool] = None
    corrective_action_due_date: Optional[datetime] = None
    status: Optional[str] = None


class AuditFindingResponse(BaseModel):
    """Schema for Audit Finding response.

    Deliberately does NOT inherit AuditFindingBase so that input-only
    validators (sanitize, min_length, pattern) don't re-run on output
    serialization and cause 500s when legacy data doesn't match.

    JSON list columns use ``list`` (not ``List[int]``) because the import
    promotion path stores clause references as strings (e.g. "8.1") while
    other paths store integer IDs.  Using an untyped list prevents Pydantic
    coercion failures on heterogeneous data.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    reference_number: Optional[str] = None
    run_id: int
    question_id: Optional[int] = None
    title: str
    description: str
    severity: str
    finding_type: str
    status: str
    clause_ids: Optional[list] = Field(None, validation_alias="clause_ids_json_legacy")
    control_ids: Optional[list] = Field(None, validation_alias="control_ids_json")
    risk_ids: Optional[list] = Field(None, validation_alias="risk_ids_json")
    corrective_action_required: bool = True
    corrective_action_due_date: Optional[datetime] = None
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class AuditFindingListResponse(BaseModel):
    """Schema for paginated audit finding list response."""

    items: List[AuditFindingResponse]
    total: int
    page: int
    page_size: int
    pages: int


# Forward references for nested models
AuditRunDetailResponse.model_rebuild()
