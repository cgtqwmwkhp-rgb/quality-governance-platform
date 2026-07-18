"""Document Campaign API Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# =============================================================================
# Engineer Groups
# =============================================================================


class GroupCreateRequest(BaseModel):
    """Request to create an engineer group."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    member_user_ids: List[int] = Field(default_factory=list)


class GroupMembersRequest(BaseModel):
    """Request to add members to an engineer group."""

    user_ids: List[int] = Field(..., min_length=1)


class GroupResponse(BaseModel):
    """Engineer group with member count."""

    id: int
    name: str
    description: Optional[str] = None
    member_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class GroupListResponse(BaseModel):
    items: List[GroupResponse]
    total: int


# =============================================================================
# Campaigns
# =============================================================================


class AudienceSpec(BaseModel):
    """Audience targeting spec for a document campaign."""

    all_users: bool = False
    department: Optional[str] = None
    role: Optional[str] = None
    group_ids: List[int] = Field(default_factory=list)
    user_ids: List[int] = Field(default_factory=list)


class CampaignCreateRequestFE(BaseModel):
    """FE Launch panel payload (#1146) — flat audience fields."""

    document_id: int
    quiz_draft_id: Optional[int] = None
    title: Optional[str] = None
    due_within_days: int = Field(14, ge=1, le=365)
    require_quiz: Optional[bool] = None
    require_sign: bool = True
    reminder_hours: Optional[List[int]] = None
    reminder_offsets_hours: Optional[List[int]] = None
    audience_type: Optional[str] = None  # all_users|department|role|group|specific_users
    audience_department: Optional[str] = None
    audience_role: Optional[str] = None
    audience_group_id: Optional[int] = None
    audience_user_ids: Optional[List[int]] = None
    audience: Optional[AudienceSpec] = None

    def to_internal(self) -> "CampaignCreateRequest":
        hours = self.reminder_offsets_hours or self.reminder_hours
        if self.audience is not None:
            aud = self.audience
        else:
            t = (self.audience_type or "all_users").lower()
            aud = AudienceSpec(
                all_users=t == "all_users",
                department=self.audience_department if t == "department" else None,
                role=self.audience_role if t == "role" else None,
                group_ids=[self.audience_group_id] if t == "group" and self.audience_group_id else [],
                user_ids=list(self.audience_user_ids or []) if t == "specific_users" else [],
            )
            if t == "all_users":
                aud.all_users = True
        return CampaignCreateRequest(
            document_id=self.document_id,
            quiz_draft_id=self.quiz_draft_id,
            title=self.title,
            due_within_days=self.due_within_days,
            require_quiz=self.require_quiz,
            require_sign=self.require_sign,
            reminder_offsets_hours=hours,
            audience=aud,
        )


class CampaignCreateRequest(BaseModel):
    """Request to create a document campaign."""

    document_id: int
    quiz_draft_id: Optional[int] = None
    title: Optional[str] = None
    due_within_days: int = Field(14, ge=1, le=365)
    require_quiz: Optional[bool] = None
    require_sign: bool = True
    reminder_offsets_hours: Optional[List[int]] = None
    audience: AudienceSpec


class CampaignResponse(BaseModel):
    """Document campaign response."""

    id: int
    document_id: int
    quiz_draft_id: Optional[int] = None
    title: Optional[str] = None
    status: str
    due_within_days: int
    require_quiz: bool
    require_sign: bool
    reminder_offsets_hours: List[int] = Field(default_factory=list)
    reminder_hours: List[int] = Field(default_factory=list)
    assigned_count: Optional[int] = None
    audience_type: Optional[str] = None
    created_at: datetime
    launched_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    # Compliance summary — only populated on GET /{id}
    total_assigned: Optional[int] = None
    completed: Optional[int] = None
    pending: Optional[int] = None
    overdue: Optional[int] = None
    expired: Optional[int] = None
    completion_rate: Optional[float] = None

    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    items: List[CampaignResponse]
    total: int


class LaunchCampaignResponse(BaseModel):
    """Response to POST /campaigns/{id}/launch."""

    campaign_id: int
    assigned_count: int
    notified_count: int
    id: Optional[int] = None
    status: Optional[str] = None
    launched_at: Optional[datetime] = None


# =============================================================================
# Assignments (My Reading)
# =============================================================================


class AssignmentResponse(BaseModel):
    """A user's campaign assignment, with document/campaign context."""

    id: int
    campaign_id: int
    document_id: int
    document_title: str
    campaign_title: Optional[str] = None
    status: str
    assigned_at: datetime
    due_at: datetime
    due_date: Optional[datetime] = None
    first_opened_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    require_quiz: bool = False
    quiz_required: bool = False
    requires_quiz: bool = False
    require_sign: bool = True
    quiz_score: Optional[int] = None
    quiz_passed: Optional[bool] = None
    quiz_attempts: int = 0


class MyAssignmentsResponse(BaseModel):
    items: List[AssignmentResponse]
    total: int


class AssignmentOpenedResponse(BaseModel):
    message: str
    first_opened_at: Optional[datetime] = None


# =============================================================================
# Quiz
# =============================================================================


class QuizQuestionOut(BaseModel):
    """A quiz question with correct-answer keys stripped."""

    type: str = "mcq"
    question: str
    options: Optional[List[str]] = None
    explanation: Optional[str] = None


class AssignmentQuizResponse(BaseModel):
    questions: List[Dict[str, Any]]
    pass_mark: int


class QuizAnswerIn(BaseModel):
    """A single answer within a quiz submission."""

    question_index: int
    selected_option: Optional[str] = None
    text_answer: Optional[str] = None


class QuizSubmitRequest(BaseModel):
    answers: List[QuizAnswerIn]


class QuizSubmitResponse(BaseModel):
    score: int
    passed: bool
    pass_mark: int


# =============================================================================
# Completion / Sign-off
# =============================================================================


class CompleteAssignmentRequest(BaseModel):
    acceptance_statement: str = Field(..., min_length=1)
    signature_data: Optional[str] = None


class CompleteAssignmentResponse(BaseModel):
    id: int
    status: str
    completed_at: Optional[datetime] = None


# =============================================================================
# Reminder defaults, compliance, evidence, question inbox
# =============================================================================


class ReminderDefaultsResponse(BaseModel):
    reminder_hours: List[int]


class ReminderDefaultsUpdateRequest(BaseModel):
    reminder_hours: List[int] = Field(..., min_length=1)


class ComplianceSummaryItem(BaseModel):
    campaign_id: int
    document_id: int
    document_title: str
    title: Optional[str] = None
    status: str
    assigned: int
    completed: int
    pending: int
    overdue: int
    completion_rate: float
    quiz_pass_count: int
    audience_group_ids: List[int] = Field(default_factory=list)
    reminder_offsets_hours: List[int] = Field(default_factory=list)
    launched_at: Optional[datetime] = None
    due_within_days: int


class ComplianceSummaryResponse(BaseModel):
    items: List[ComplianceSummaryItem]
    total: int


class QuestionInboxItem(BaseModel):
    document_id: int
    document_title: str
    thread_id: int
    thread_title: Optional[str] = None
    status: str
    created_at: datetime
    created_by_id: int
    latest_message_preview: Optional[str] = None


class QuestionInboxResponse(BaseModel):
    items: List[QuestionInboxItem]
    total: int


class AskAssignmentQuestionRequest(BaseModel):
    title: Optional[str] = None
    body: str = Field(..., min_length=1)


class QuestionThreadResponse(BaseModel):
    id: int
    document_id: int
    title: Optional[str] = None
    status: str
    created_by_id: int
    created_at: datetime


class QuestionReplyRequest(BaseModel):
    body: str = Field(..., min_length=1)


class QuestionMessageResponse(BaseModel):
    id: int
    thread_id: int
    author_id: int
    body: str
    created_at: datetime

class SnoozeAssignmentRequest(BaseModel):
    hours: int = Field(..., ge=1, le=168)


class SnoozeAssignmentResponse(BaseModel):
    id: int
    snooze_until: datetime
    message: str = "Assignment snoozed"


class GroupComplianceItem(BaseModel):
    group_id: Optional[int] = None
    group_name: str
    assigned: int
    completed: int
    pending: int
    overdue: int
    quiz_pass_count: int
    completion_rate: float


class GroupComplianceResponse(BaseModel):
    campaign_id: int
    items: List[GroupComplianceItem]
    total: int

