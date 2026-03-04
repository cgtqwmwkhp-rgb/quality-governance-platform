"""Pydantic schemas for Engineer API."""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ============== Engineer Schemas ==============


class EngineerCreate(BaseModel):
    """Schema for creating an engineer."""

    user_id: int
    employee_number: Optional[str] = Field(None, max_length=50)
    job_title: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    site: Optional[str] = Field(None, max_length=200)
    start_date: Optional[datetime] = None
    specialisations: Optional[List[Any]] = None
    certifications: Optional[List[Any]] = None


class EngineerUpdate(BaseModel):
    """Schema for updating an engineer - all fields optional."""

    user_id: Optional[int] = None
    employee_number: Optional[str] = Field(None, max_length=50)
    job_title: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    site: Optional[str] = Field(None, max_length=200)
    start_date: Optional[datetime] = None
    specialisations: Optional[List[Any]] = None
    certifications: Optional[List[Any]] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class EngineerResponse(BaseModel):
    """Schema for engineer response - all fields from model."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    user_id: int
    employee_number: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    site: Optional[str] = None
    start_date: Optional[datetime] = None
    specialisations_json: Optional[List[Any]] = None
    certifications_json: Optional[List[Any]] = None
    is_active: bool
    notes: Optional[str] = None
    tenant_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


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
