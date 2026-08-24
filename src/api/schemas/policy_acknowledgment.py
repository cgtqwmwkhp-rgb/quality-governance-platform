"""Policy Acknowledgment API Schemas."""

from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


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
    """Schema for creating an acknowledgment requirement.

    ``extra="forbid"`` so a misspelled or unsupported field fails loudly instead
    of the requirement being created while the unknown key is silently dropped (B-10).
    """

    model_config = ConfigDict(extra="forbid")


class AcknowledgmentRequirementResponse(BaseModel):
    """Response schema for acknowledgment requirements.

    Does NOT inherit from AcknowledgmentRequirementBase to prevent
    Field validators (ge, le) from triggering 500 errors on response serialisation.
    """

    id: int
    policy_id: int
    acknowledgment_type: str = "read_only"
    required_for_all: bool = False
    required_departments: Optional[List[str]] = None
    required_roles: Optional[List[str]] = None
    required_user_ids: Optional[List[int]] = None
    due_within_days: int = 30
    reminder_days_before: Optional[List[int]] = None
    re_acknowledge_on_update: bool = True
    re_acknowledge_period_months: Optional[int] = None
    quiz_questions: Optional[List[Dict[str, Any]]] = None
    quiz_passing_score: int = 80
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


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
    """Request to record an acknowledgment.

    ``extra="forbid"`` so a misspelled or unsupported field fails loudly instead
    of the acknowledgment being saved while the unknown key is silently dropped (B-10).
    """

    model_config = ConfigDict(extra="forbid")

    quiz_score: Optional[int] = None
    acceptance_statement: Optional[str] = None
    signature_data: Optional[str] = None


class AssignAcknowledgmentRequest(BaseModel):
    """Request to assign acknowledgments to users.

    ``extra="forbid"`` so a misspelled or unsupported field fails loudly instead
    of assignments proceeding while the unknown key is silently dropped (B-10).
    """

    model_config = ConfigDict(extra="forbid")

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


class ComplianceDashboardMetrics(BaseModel):
    """Counts that were actually read from the database."""

    total_assignments: int
    completed: int
    pending: int
    overdue: int
    completion_rate: float
    overdue_rate: float


class MeasuredComplianceDashboard(BaseModel):
    """A real measurement. Every count in ``metrics`` came from a query that ran."""

    measurement: Literal["measured"] = "measured"
    metrics: ComplianceDashboardMetrics


class UnmeasurableComplianceDashboard(BaseModel):
    """No measurement was possible, so this variant carries no numbers at all.

    ``metrics`` is absent rather than zeroed or nulled: a caller reading
    ``body["metrics"]["completion_rate"]`` raises instead of receiving a 0 that
    would be indistinguishable from "nobody has acknowledged anything".
    """

    measurement: Literal["unmeasurable"] = "unmeasurable"
    reason: str
    missing_tables: List[str]


# Discriminated, so the two states are distinguished by the payload's shape rather
# than by a sentinel value a consumer can coerce. There is deliberately no variant
# that carries both a number and a "this is not a real number" flag.
ComplianceDashboardResponse = Annotated[
    Union[MeasuredComplianceDashboard, UnmeasurableComplianceDashboard],
    Field(discriminator="measurement"),
]
