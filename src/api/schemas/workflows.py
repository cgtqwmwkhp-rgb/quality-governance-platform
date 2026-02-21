from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class WorkflowTemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    steps: list[dict[str, Any]] = []

    class Config:
        from_attributes = True


class WorkflowInstanceResponse(BaseModel):
    id: int
    template_id: int
    status: str
    current_step: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApprovalResponse(BaseModel):
    id: int
    status: str
    approved_by: Optional[int] = None
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class DelegationResponse(BaseModel):
    id: int
    delegated_by: int
    delegated_to: int
    active: bool = True

    class Config:
        from_attributes = True


class WorkflowStatsResponse(BaseModel):
    total_workflows: int = 0
    active_workflows: int = 0
    completed_workflows: int = 0
    pending_approvals: int = 0
