"""API schemas for Enterprise Risk Register XLSX import (RR-W4)."""

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class RiskRegisterImportRowError(BaseModel):
    row: int
    code: str
    message: str
    field: Optional[str] = None


class RiskRegisterImportPreviewRow(BaseModel):
    row: int
    action: str
    reference: str
    title: str
    category: str
    inherent_score: int
    residual_score: int
    risk_owner_name: Optional[str] = None
    status: str = "active"


class RiskRegisterImportValidationReportResponse(BaseModel):
    dry_run: bool
    total_rows: int
    valid_rows: int
    error_rows: int
    creates: int
    updates: int
    ok: bool
    errors: List[RiskRegisterImportRowError] = Field(default_factory=list)
    preview: List[RiskRegisterImportPreviewRow] = Field(default_factory=list)
    action_plan_skipped: bool = True


class RiskRegisterImportCommitResponse(BaseModel):
    created_count: int
    updated_count: int
    created_risk_ids: List[int]
    updated_risk_ids: List[int]
    report: RiskRegisterImportValidationReportResponse


class RiskRegisterImportValidationErrorDetail(BaseModel):
    """422 payload mirror when commit is blocked by row errors."""

    detail: Any
