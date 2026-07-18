"""Pydantic schemas for Engineer API."""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ============== Engineer Schemas ==============


class EngineerCreate(BaseModel):
    """Schema for creating an engineer."""

    user_id: Optional[int] = None
    display_name: Optional[str] = Field(None, max_length=200)
    employee_number: Optional[str] = Field(None, max_length=50)
    job_title: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    site: Optional[str] = Field(None, max_length=200)
    start_date: Optional[datetime] = None
    specialisations: Optional[List[Any]] = None
    certifications: Optional[List[Any]] = None

    @model_validator(mode="before")
    @classmethod
    def map_role_to_job_title(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("role") and not data.get("job_title"):
            data = dict(data)
            data["job_title"] = data["role"]
        return data

    @model_validator(mode="after")
    def require_user_or_display_name(self) -> "EngineerCreate":
        if self.user_id is None and not (self.display_name and self.display_name.strip()):
            raise ValueError("Either user_id or display_name is required")
        return self


class EngineerUpdate(BaseModel):
    """Schema for updating an engineer - QGP pseudo-DB only (never writes PAMS)."""

    user_id: Optional[int] = None
    display_name: Optional[str] = Field(None, max_length=200)
    employee_number: Optional[str] = Field(None, max_length=50)
    job_title: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    site: Optional[str] = Field(None, max_length=200)
    start_date: Optional[datetime] = None
    specialisations: Optional[List[Any]] = None
    certifications: Optional[List[Any]] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    qgp_profile_override: Optional[bool] = None


class EngineerLinkUserRequest(BaseModel):
    """Link a QGP login User to an Engineer person record."""

    user_id: int


class LinkedUserSummary(BaseModel):
    """Optional login seat summary for pickers (Person may exist without this)."""

    id: int
    email: str
    full_name: Optional[str] = None


class EngineerResponse(BaseModel):
    """Schema for engineer response - all fields from model."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    user_id: Optional[int] = None
    display_name: Optional[str] = None
    pams_technician_id: Optional[int] = None
    employee_number: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    site: Optional[str] = None
    start_date: Optional[datetime] = None
    specialisations_json: Optional[List[Any]] = None
    certifications_json: Optional[List[Any]] = None
    is_active: bool
    notes: Optional[str] = None
    qgp_profile_override: bool = False
    tenant_id: int | None = None
    created_at: datetime
    updated_at: datetime
    linked_user: Optional[LinkedUserSummary] = None

    @field_validator("qgp_profile_override", mode="before")
    @classmethod
    def coerce_qgp_override(cls, value: Any) -> bool:
        return bool(value) if value is not None else False


class EngineerLinkStatusResponse(BaseModel):
    """Honest self-resolve for portal inbox: linked profile or explicit unlinked state."""

    linked: bool
    id: Optional[int] = None
    external_id: Optional[str] = None
    user_id: Optional[int] = None
    employee_number: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    site: Optional[str] = None
    start_date: Optional[datetime] = None
    specialisations_json: Optional[List[Any]] = None
    certifications_json: Optional[List[Any]] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    tenant_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_engineer(cls, engineer: object) -> "EngineerLinkStatusResponse":
        profile = EngineerResponse.model_validate(engineer)
        return cls(linked=True, **profile.model_dump())

    @classmethod
    def unlinked(cls) -> "EngineerLinkStatusResponse":
        return cls(linked=False)


class PamsTechnicianSyncResponse(BaseModel):
    """Result counts from PAMS technicians_store sync."""

    created: int
    updated: int
    deactivated: int
    skipped: int
    errors: int


class EngineerListResponse(BaseModel):
    """Schema for paginated engineer list."""

    items: List[EngineerResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============== Competency Record Schema ==============


class CompetencyRecordResponse(BaseModel):
    """Schema for competency record response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    engineer_id: int
    asset_type_id: int
    template_id: int
    source_type: str
    source_run_id: str
    state: str
    outcome: Optional[str] = None
    assessed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class SkillsMatrixEntry(BaseModel):
    """Single entry in the skills matrix (engineer competency per asset type)."""

    asset_type_id: int
    asset_type_name: Optional[str] = None
    state: str
    outcome: Optional[str] = None
    assessed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class SkillsMatrixResponse(BaseModel):
    """Skills matrix: engineer competency across asset types."""

    engineer_id: int
    matrix: List[SkillsMatrixEntry]


# ============== Competency Requirement Schemas ==============


class CompetencyRequirementCreate(BaseModel):
    """Create a competency requirement (frequency + allocation filters)."""

    asset_type_id: int
    template_id: int
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    is_mandatory: bool = True
    reassessment_interval_days: int = Field(365, ge=1, le=3650)
    role_key: Optional[str] = Field(None, max_length=100)
    site: Optional[str] = Field(None, max_length=200)


class CompetencyRequirementUpdate(BaseModel):
    """Partial update for a competency requirement."""

    asset_type_id: Optional[int] = None
    template_id: Optional[int] = None
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    is_mandatory: Optional[bool] = None
    reassessment_interval_days: Optional[int] = Field(None, ge=1, le=3650)
    role_key: Optional[str] = Field(None, max_length=100)
    site: Optional[str] = Field(None, max_length=200)


class CompetencyRequirementResponse(BaseModel):
    """Competency requirement response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_type_id: int
    template_id: int
    name: str
    description: Optional[str] = None
    is_mandatory: bool
    reassessment_interval_days: int
    role_key: Optional[str] = None
    site: Optional[str] = None
    tenant_id: int
    created_at: datetime
    updated_at: datetime


class CompetencyRequirementListResponse(BaseModel):
    """Paginated competency requirements."""

    items: List[CompetencyRequirementResponse]
    total: int
    page: int
    page_size: int
    pages: int


class CompetencyRequirementAllocateRequest(BaseModel):
    """Allocate a requirement to engineers (explicit ids and/or site/role filters)."""

    engineer_ids: Optional[List[int]] = None
    match_site: bool = True
    match_role_key: Optional[str] = Field(None, max_length=100)
    due_days: Optional[int] = Field(None, ge=1, le=3650)


class CompetencyRequirementAllocateResponse(BaseModel):
    """Allocation result."""

    requirement_id: int
    created_checklist_ids: List[int]
    skipped_engineer_ids: List[int]
    matched_engineer_ids: List[int]


# ============== Training Ticket Schemas ==============


class TrainingTicketCreate(BaseModel):
    """Create a first-class training ticket."""

    engineer_id: int
    scheme: str = Field(..., max_length=100)
    ticket_number: str = Field(..., max_length=100)
    issuer: Optional[str] = Field(None, max_length=200)
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    verify_state: str = Field(default="unverified", pattern="^(unverified|pending|verified|rejected|expired)$")
    evidence_id: Optional[int] = None
    notes: Optional[str] = None


class TrainingTicketUpdate(BaseModel):
    """Partial update for a training ticket."""

    scheme: Optional[str] = Field(None, max_length=100)
    ticket_number: Optional[str] = Field(None, max_length=100)
    issuer: Optional[str] = Field(None, max_length=200)
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    verify_state: Optional[str] = Field(None, pattern="^(unverified|pending|verified|rejected|expired)$")
    evidence_id: Optional[int] = None
    notes: Optional[str] = None


class TrainingTicketResponse(BaseModel):
    """Training ticket response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    engineer_id: int
    scheme: str
    ticket_number: str
    issuer: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    verify_state: str
    evidence_id: Optional[int] = None
    notes: Optional[str] = None
    tenant_id: int
    created_at: datetime
    updated_at: datetime


class TrainingTicketListResponse(BaseModel):
    """Paginated training tickets."""

    items: List[TrainingTicketResponse]
    total: int
    page: int
    page_size: int
    pages: int
