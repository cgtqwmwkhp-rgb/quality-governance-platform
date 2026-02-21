"""Investigation API schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from src.domain.models.investigation import AssignedEntityType, InvestigationStatus

# Investigation Template Schemas


class InvestigationTemplateBase(BaseModel):
    """Base schema for investigation templates."""

    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    version: str = Field(default="1.0", description="Template version")
    is_active: bool = Field(default=True, description="Whether template is active")
    structure: Dict[str, Any] = Field(..., description="Template structure (sections and fields)")
    applicable_entity_types: List[str] = Field(..., description="Entity types this template applies to")

    @field_validator("applicable_entity_types")
    @classmethod
    def validate_entity_types(cls, v: List[str]) -> List[str]:
        """Validate entity types are valid."""
        valid_types = {e.value for e in AssignedEntityType}
        for entity_type in v:
            if entity_type not in valid_types:
                raise ValueError(f"Invalid entity type: {entity_type}. Must be one of {valid_types}")
        return v


class InvestigationTemplateCreate(InvestigationTemplateBase):
    """Schema for creating an investigation template."""

    pass


class InvestigationTemplateUpdate(BaseModel):
    """Schema for updating an investigation template."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None
    structure: Optional[Dict[str, Any]] = None
    applicable_entity_types: Optional[List[str]] = None

    @field_validator("applicable_entity_types")
    @classmethod
    def validate_entity_types(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate entity types are valid."""
        if v is None:
            return v
        valid_types = {e.value for e in AssignedEntityType}
        for entity_type in v:
            if entity_type not in valid_types:
                raise ValueError(f"Invalid entity type: {entity_type}. Must be one of {valid_types}")
        return v


class InvestigationTemplateResponse(InvestigationTemplateBase):
    """Schema for investigation template response."""

    id: int
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None
    updated_by_id: Optional[int] = None

    class Config:
        from_attributes = True


class InvestigationTemplateListResponse(BaseModel):
    """Schema for paginated investigation template list."""

    items: List[InvestigationTemplateResponse]
    total: int
    page: int
    page_size: int
    pages: int


# Investigation Run Schemas


class InvestigationRunBase(BaseModel):
    """Base schema for investigation runs."""

    template_id: int = Field(..., description="Investigation template ID")
    assigned_entity_type: str = Field(..., description="Entity type (RTA, incident, complaint)")
    assigned_entity_id: int = Field(..., description="Entity ID")
    title: str = Field(..., min_length=1, max_length=255, description="Investigation title")
    description: Optional[str] = Field(None, description="Investigation description")
    status: str = Field(default="draft", description="Investigation status")
    data: Dict[str, Any] = Field(default_factory=dict, description="Investigation data (responses)")

    @field_validator("assigned_entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        """Validate entity type is valid."""
        valid_types = {e.value for e in AssignedEntityType}
        if v not in valid_types:
            raise ValueError(f"Invalid entity type: {v}. Must be one of {valid_types}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is valid."""
        valid_statuses = {s.value for s in InvestigationStatus}
        if v not in valid_statuses:
            raise ValueError(f"Invalid status: {v}. Must be one of {valid_statuses}")
        return v


class InvestigationRunCreate(InvestigationRunBase):
    """Schema for creating an investigation run."""

    pass


class InvestigationRunUpdate(BaseModel):
    """Schema for updating an investigation run."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    assigned_to_user_id: Optional[int] = None
    reviewer_user_id: Optional[int] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate status is valid."""
        if v is None:
            return v
        valid_statuses = {s.value for s in InvestigationStatus}
        if v not in valid_statuses:
            raise ValueError(f"Invalid status: {v}. Must be one of {valid_statuses}")
        return v


class InvestigationRunResponse(InvestigationRunBase):
    """Schema for investigation run response."""

    id: int
    reference_number: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    assigned_to_user_id: Optional[int] = None
    reviewer_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None
    updated_by_id: Optional[int] = None

    class Config:
        from_attributes = True


class InvestigationRunListResponse(BaseModel):
    """Schema for paginated investigation run list."""

    items: List[InvestigationRunResponse]
    total: int
    page: int
    page_size: int
    pages: int


# === Stage 2.1: From-Record Schemas ===


class CreateFromRecordRequest(BaseModel):
    """Request schema for creating investigation from source record."""

    source_type: str = Field(
        ..., description="Source record type (near_miss, road_traffic_collision, complaint, reporting_incident)"
    )
    source_id: int = Field(..., gt=0, description="Source record ID")
    title: str = Field(..., min_length=1, max_length=255, description="Investigation title")
    template_id: int = Field(default=1, description="Template ID (default: v2.1)")

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        """Validate source type is valid."""
        valid_types = {e.value for e in AssignedEntityType}
        if v not in valid_types:
            raise ValueError(f"Invalid source type: {v}. Must be one of {valid_types}")
        return v


class SourceRecordItem(BaseModel):
    """Single source record for dropdown selection."""

    source_id: int = Field(..., description="Source record ID")
    display_label: str = Field(..., description="Display label for dropdown")
    reference_number: str = Field(..., description="Record reference number")
    status: str = Field(..., description="Record status")
    created_at: datetime = Field(..., description="Record creation date")
    investigation_id: Optional[int] = Field(None, description="Linked investigation ID if exists")
    investigation_reference: Optional[str] = Field(None, description="Investigation reference if exists")


class SourceRecordsResponse(BaseModel):
    """Response for source records listing."""

    items: List[SourceRecordItem]
    total: int
    page: int
    page_size: int
    pages: int
    source_type: str


# === Stage 1: Timeline, Comments, Packs, Closure Validation Schemas ===


class TimelineEventResponse(BaseModel):
    """Single timeline event (revision event)."""

    id: int
    created_at: datetime
    event_type: str = Field(..., description="Event type: CREATED, DATA_UPDATED, STATUS_CHANGED, etc.")
    field_path: Optional[str] = Field(None, description="Field path that changed (for DATA_UPDATED)")
    old_value: Optional[Dict[str, Any]] = Field(None, description="Previous value")
    new_value: Optional[Dict[str, Any]] = Field(None, description="New value")
    actor_id: int = Field(..., description="User ID who performed the action")
    version: int = Field(..., description="Investigation version at time of event")
    event_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional context")

    class Config:
        from_attributes = True


class TimelineListResponse(BaseModel):
    """Paginated list of timeline events."""

    items: List[TimelineEventResponse]
    total: int
    page: int
    page_size: int
    investigation_id: int


class CommentCreateRequest(BaseModel):
    """Request schema for adding a comment to an investigation.

    Accepts 'body' field to match frontend API contract.
    """

    body: str = Field(..., min_length=1, max_length=10000, description="Comment content")
    section_id: Optional[str] = Field(None, description="Section to attach comment to")
    field_id: Optional[str] = Field(None, description="Field to attach comment to")
    parent_comment_id: Optional[int] = Field(None, description="Parent comment ID for threading")


class CommentResponse(BaseModel):
    """Single comment on an investigation."""

    id: int
    created_at: datetime
    content: str = Field(..., description="Comment content")
    author_id: int = Field(..., description="Author user ID")
    section_id: Optional[str] = Field(None, description="Section this comment is attached to")
    field_id: Optional[str] = Field(None, description="Field this comment is attached to")
    parent_comment_id: Optional[int] = Field(None, description="Parent comment ID for threading")

    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    """Paginated list of comments."""

    items: List[CommentResponse]
    total: int
    page: int
    page_size: int
    investigation_id: int


class CustomerPackSummaryResponse(BaseModel):
    """Summary of a customer pack (without full content for listing)."""

    id: int
    created_at: datetime
    pack_uuid: str = Field(..., description="Unique pack identifier")
    audience: str = Field(..., description="Pack audience: internal_customer or external_customer")
    checksum_sha256: str = Field(..., description="Content checksum for integrity")
    generated_by_id: int = Field(..., description="User who generated the pack")
    expires_at: Optional[datetime] = Field(None, description="Pack expiry date if set")

    class Config:
        from_attributes = True


class PackListResponse(BaseModel):
    """Paginated list of customer packs."""

    items: List[CustomerPackSummaryResponse]
    total: int
    page: int
    page_size: int
    investigation_id: int


class CustomerPackGeneratedResponse(BaseModel):
    """Response schema for a generated customer pack."""

    pack_id: int
    pack_uuid: str
    audience: str
    investigation_id: int
    investigation_reference: Optional[str] = None
    generated_at: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    redaction_log: Optional[List[Any]] = None
    included_assets: Optional[List[Any]] = None
    checksum: Optional[str] = None


class AutosaveRequest(BaseModel):
    """Request schema for autosaving investigation data with optimistic locking."""

    data: Dict[str, Any] = Field(..., description="Investigation data to save")
    version: int = Field(..., gt=0, description="Expected version for optimistic locking")


class ClosureValidationResponse(BaseModel):
    """Result of closure validation check."""

    status: str = Field(..., description="OK or BLOCKED")
    reason_codes: List[str] = Field(default_factory=list, description="List of blocking reason codes")
    missing_fields: List[str] = Field(default_factory=list, description="List of missing required fields")
    checked_at_utc: datetime = Field(..., description="Timestamp of validation check")
    investigation_id: int
    investigation_level: Optional[str] = Field(None, description="Investigation level (LOW/MEDIUM/HIGH)")
