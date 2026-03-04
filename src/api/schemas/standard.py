"""Pydantic schemas for Standards Library API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ControlBase(BaseModel):
    """Base schema for Control."""

    control_number: str = Field(..., min_length=1, max_length=20)
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    implementation_guidance: Optional[str] = None
    is_applicable: bool = True
    applicability_justification: Optional[str] = None
    implementation_status: Optional[str] = None


class ControlCreate(ControlBase):
    """Schema for creating a Control."""

    clause_id: int


class ControlUpdate(BaseModel):
    """Schema for updating a Control."""

    control_number: Optional[str] = Field(None, min_length=1, max_length=20)
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    implementation_guidance: Optional[str] = None
    is_applicable: Optional[bool] = None
    applicability_justification: Optional[str] = None
    implementation_status: Optional[str] = None
    is_active: Optional[bool] = None


class ControlResponse(ControlBase):
    """Schema for Control response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    clause_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClauseBase(BaseModel):
    """Base schema for Clause."""

    clause_number: str = Field(..., min_length=1, max_length=20)
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    level: int = 1
    sort_order: int = 0


class ClauseCreate(ClauseBase):
    """Schema for creating a Clause."""

    standard_id: int
    parent_clause_id: Optional[int] = None


class ClauseUpdate(BaseModel):
    """Schema for updating a Clause."""

    clause_number: Optional[str] = Field(None, min_length=1, max_length=20)
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    parent_clause_id: Optional[int] = None
    level: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class ClauseResponse(ClauseBase):
    """Schema for Clause response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    standard_id: int
    parent_clause_id: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    controls: List[ControlResponse] = []


class StandardBase(BaseModel):
    """Base schema for Standard."""

    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=200)
    full_name: str = Field(..., min_length=1, max_length=500)
    version: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = None
    effective_date: Optional[str] = None


class StandardCreate(StandardBase):
    """Schema for creating a Standard."""

    pass


class StandardUpdate(BaseModel):
    """Schema for updating a Standard."""

    code: Optional[str] = Field(None, min_length=1, max_length=20)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    full_name: Optional[str] = Field(None, min_length=1, max_length=500)
    version: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = None
    effective_date: Optional[str] = None
    is_active: Optional[bool] = None


class StandardResponse(StandardBase):
    """Schema for Standard response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StandardDetailResponse(StandardResponse):
    """Schema for detailed Standard response with clauses."""

    clauses: List[ClauseResponse] = []


class StandardListResponse(BaseModel):
    """Schema for paginated standard list response."""

    items: List[StandardResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ComplianceScoreResponse(BaseModel):
    """Schema for compliance score response."""

    standard_id: int
    standard_code: str
    total_controls: int
    implemented_count: int
    partial_count: int
    not_implemented_count: int
    compliance_percentage: int
    setup_required: bool


class ControlListItem(BaseModel):
    """Schema for control list item (flat view for aggregation)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    clause_id: int
    clause_number: str
    control_number: str
    title: str
    implementation_status: Optional[str] = None
    is_applicable: bool
    is_active: bool
