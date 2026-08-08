"""Pydantic schemas for Job Lifecycle axes (JL-1 / ADR-0022)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobTypeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class JobTypeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class JobTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    code: str
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JobTypeListResponse(BaseModel):
    items: List[JobTypeResponse]
    total: int


class JobLaneCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class JobLaneUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class JobLaneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    job_type_id: int
    code: str
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JobLaneListResponse(BaseModel):
    items: List[JobLaneResponse]
    total: int


class JobStepCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class JobStepUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class JobStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    job_type_id: int
    code: str
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JobStepListResponse(BaseModel):
    items: List[JobStepResponse]
    total: int


class JobCellDocumentsPut(BaseModel):
    """Replace the cell's ``library_document_id[]`` membership."""

    model_config = ConfigDict(extra="forbid")

    library_document_ids: List[int] = Field(default_factory=list)


class JobCellResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    job_type_id: int
    lane_id: int
    step_id: int
    library_document_ids: List[int] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class JobCellListResponse(BaseModel):
    items: List[JobCellResponse]
    total: int


__all__ = [
    "JobCellDocumentsPut",
    "JobCellListResponse",
    "JobCellResponse",
    "JobLaneCreate",
    "JobLaneListResponse",
    "JobLaneResponse",
    "JobLaneUpdate",
    "JobStepCreate",
    "JobStepListResponse",
    "JobStepResponse",
    "JobStepUpdate",
    "JobTypeCreate",
    "JobTypeListResponse",
    "JobTypeResponse",
    "JobTypeUpdate",
]
