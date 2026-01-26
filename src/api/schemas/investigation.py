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
    total_pages: int


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
    total_pages: int


# === Stage 2.1: From-Record Schemas ===


class CreateFromRecordRequest(BaseModel):
    """Request schema for creating investigation from source record."""

    source_type: str = Field(..., description="Source record type (near_miss, road_traffic_collision, complaint, reporting_incident)")
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
    total_pages: int
    source_type: str
