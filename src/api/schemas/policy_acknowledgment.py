"""Policy Acknowledgment API Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AcknowledgmentRequirementBase(BaseModel):
    """Base schema for acknowledgment requirements."""
    policy_id: int
    acknowledgment_type: str = Field("read_only", description="Type: read_only, accept, quiz, sign")
    required_for_all: bool = False
    required_departments: Optional[List[str]] = None
    required_roles: Optional[List[str]] = None
    required_user_ids: Optional[List[int]] = None
    due_within_days: int = Field(30, ge=1, le=365)
    reminder_days_before: Optional[List[int]] = Field(None, description="Days before due to send reminders")
    re_acknowledge_on_update: bool = True
    re_acknowledge_period_months: Optional[int] = None
    quiz_questions: Optional[List[Dict[str, Any]]] = None
    quiz_passing_score: int = Field(80, ge=0, le=100)
    is_active: bool = True


class AcknowledgmentRequirementCreate(AcknowledgmentRequirementBase):
    """Schema for creating an acknowledgment requirement."""
    pass


class AcknowledgmentRequirementResponse(AcknowledgmentRequirementBase):
    """Schema for acknowledgment requirement response."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PolicyAcknowledgmentBase(BaseModel):
    """Base schema for policy acknowledgment."""
    requirement_id: int
    policy_id: int
    user_id: int
    policy_version: Optional[str] = None
    status: str = "pending"
    due_date: datetime


class PolicyAcknowledgmentResponse(BaseModel):
    """Schema for policy acknowledgment response."""
    id: int
    requirement_id: int
    policy_id: int
    user_id: int
    policy_version: Optional[str] = None
    status: str
    assigned_at: datetime
    due_date: datetime
    acknowledged_at: Optional[datetime] = None
    first_opened_at: Optional[datetime] = None
    time_spent_seconds: Optional[int] = None
    quiz_score: Optional[int] = None
    quiz_attempts: int = 0
    quiz_passed: Optional[bool] = None
    reminders_sent: int = 0

    class Config:
        from_attributes = True


class PolicyAcknowledgmentListResponse(BaseModel):
    """List response for policy acknowledgments."""
    items: List[PolicyAcknowledgmentResponse]
    total: int


class RecordAcknowledgmentRequest(BaseModel):
    """Request to record an acknowledgment."""
    quiz_score: Optional[int] = None
    acceptance_statement: Optional[str] = None
    signature_data: Optional[str] = None


class AssignAcknowledgmentRequest(BaseModel):
    """Request to assign acknowledgments to users."""
    user_ids: List[int]
    policy_version: Optional[str] = None


class PolicyAcknowledgmentStatusResponse(BaseModel):
    """Status summary for a policy's acknowledgments."""
    policy_id: int
    total_assigned: int
    completed: int
    pending: int
    overdue: int
    completion_rate: float


class DocumentReadLogResponse(BaseModel):
    """Schema for document read log."""
    id: int
    document_type: str
    document_id: int
    document_version: Optional[str] = None
    user_id: int
    accessed_at: datetime
    duration_seconds: Optional[int] = None
    scroll_percentage: Optional[int] = None
    device_type: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentReadLogListResponse(BaseModel):
    """List response for document read logs."""
    items: List[DocumentReadLogResponse]
    total: int


class LogDocumentReadRequest(BaseModel):
    """Request to log a document read."""
    document_type: str
    document_id: int
    document_version: Optional[str] = None
    duration_seconds: Optional[int] = None
    scroll_percentage: Optional[int] = Field(None, ge=0, le=100)
    device_type: Optional[str] = None


class ComplianceDashboardResponse(BaseModel):
    """Schema for compliance dashboard."""
    total_assignments: int
    completed: int
    pending: int
    overdue: int
    completion_rate: float
    overdue_rate: float
