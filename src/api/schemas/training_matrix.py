"""Pydantic schemas for training matrix compliance APIs."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TrainingMatrixImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    person_count: int
    course_count: int
    cell_count: int
    nonempty_cell_count: int
    expiry_without_passed_count: int
    created_at: Optional[datetime] = None
    uploaded_by_user_id: Optional[int] = None
    uploaded_by_name: Optional[str] = None
    uploaded_by_email: Optional[str] = None


class TrainingMatrixImportQaResponse(BaseModel):
    import_id: int
    expiry_without_passed_count: int
    expiry_without_passed_before_today: int
    expiry_without_passed_after_today: int
    expiry_without_passed_before_pct: float
    expiry_without_passed_after_pct: float
    all_expiry_count: int
    all_expiry_before_today: int
    all_expiry_after_today: int
    all_expiry_before_pct: float
    all_expiry_after_pct: float


class TrainingMatrixNameMapItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    atlas_name: str
    department: Optional[str] = None
    engineer_id: Optional[int] = None
    engineer_display_name: Optional[str] = None
    mapped: bool = False


class TrainingMatrixNameMapUpsert(BaseModel):
    atlas_name: str
    engineer_id: int


class TrainingMatrixRequirementCreate(BaseModel):
    match_department: Optional[str] = None
    match_role_key: Optional[str] = None
    course_key: str
    course_display_name: str
    frequency_years: int = Field(default=1, ge=1, le=5)
    is_active: bool = True
    notes: Optional[str] = None


class TrainingMatrixRequirementUpdate(BaseModel):
    match_department: Optional[str] = None
    match_role_key: Optional[str] = None
    course_display_name: Optional[str] = None
    frequency_years: Optional[int] = Field(default=None, ge=1, le=5)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class TrainingMatrixRequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_department: Optional[str] = None
    match_role_key: Optional[str] = None
    course_key: str
    course_display_name: str
    frequency_years: int
    is_active: bool
    notes: Optional[str] = None


class TrainingMatrixRequirementListResponse(BaseModel):
    items: List[TrainingMatrixRequirementResponse]
    total: int


class TrainingMatrixRequirementSeedRequest(BaseModel):
    """Populate DB requirement rows from a named SoR template (editable after)."""

    template: str = Field(default="plantexpand_2024_v1")
    mode: str = Field(
        default="fill_missing",
        description="fill_missing | refresh_template",
    )


class TrainingMatrixRequirementSeedResponse(BaseModel):
    template_id: str
    template_label: str
    created: int
    skipped_existing: int
    unmatched_modules: List[str]
    created_without_atlas_match: int


class TrainingMatrixComplianceRow(BaseModel):
    atlas_name: str
    department: Optional[str] = None
    engineer_id: Optional[int] = None
    engineer_display_name: Optional[str] = None
    course_key: str
    course_display_name: str
    frequency_years: int
    status: str
    atlas_status: Optional[str] = None
    passed_on: Optional[date] = None
    expires_on: Optional[date] = None
    qgp_due_on: Optional[date] = None
    expiry_without_passed: bool = False
    atlas_hub_url: str
    last_training_notified_at: Optional[datetime] = None


class TrainingMatrixComplianceListResponse(BaseModel):
    items: List[TrainingMatrixComplianceRow]
    total: int
    atlas_hub_url: str
    import_id: Optional[int] = None


class TrainingMatrixCourseOption(BaseModel):
    course_key: str
    display_name: str


class TrainingMatrixMatrixCell(BaseModel):
    """One dept/role x course cell in the interactive Admin frequency matrix."""

    match_department: str
    course_key: str
    course_display_name: str
    frequency_years: Optional[int] = Field(default=None, ge=0, le=5)


class TrainingMatrixMatrixUpsertRequest(BaseModel):
    cells: List[TrainingMatrixMatrixCell]


class TrainingMatrixMatrixUpsertResponse(BaseModel):
    upserted: int
    deactivated: int


class TrainingMatrixNotifyRequest(BaseModel):
    atlas_names: List[str] = Field(min_length=1)
    message: Optional[str] = None


class TrainingMatrixNotifyResponse(BaseModel):
    sent: int
    skipped: int
    failed: int
