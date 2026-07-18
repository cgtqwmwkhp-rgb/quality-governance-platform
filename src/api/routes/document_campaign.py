"""Document Campaign API Routes.

Engineer groups, document campaigns (read/quiz/sign-off), audience launch,
and the per-engineer assignment APIs (open, quiz, complete) used by "My Reading".
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from src.api.deps import CurrentUser, DbSession, require_permission
from src.api.schemas.document_campaign import (
    AskAssignmentQuestionRequest,
    AssignmentOpenedResponse,
    AssignmentQuizResponse,
    AssignmentResponse,
    CampaignCreateRequestFE,
    CampaignListResponse,
    CampaignResponse,
    CompleteAssignmentRequest,
    CompleteAssignmentResponse,
    ComplianceSummaryItem,
    ComplianceSummaryResponse,
    GroupComplianceItem,
    GroupComplianceResponse,
    GroupCreateRequest,
    GroupListResponse,
    GroupMembersRequest,
    GroupResponse,
    LaunchCampaignResponse,
    MyAssignmentsResponse,
    QuestionInboxItem,
    QuestionInboxResponse,
    QuestionMessageResponse,
    QuestionReplyRequest,
    QuestionThreadResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    ReminderDefaultsResponse,
    ReminderDefaultsUpdateRequest,
    SnoozeAssignmentRequest,
    SnoozeAssignmentResponse,
)
from src.api.utils.tenant import require_tenant_id
from src.domain.models.document_campaign import DocumentCampaign, EngineerGroup
from src.domain.models.user import User
from src.domain.services.document_campaign_service import DocumentCampaignService

router = APIRouter(prefix="/document-campaigns", tags=["Document Campaigns"])


def _group_to_response(group: EngineerGroup, member_count: int) -> GroupResponse:
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        member_count=member_count,
        created_at=group.created_at,
    )


def _campaign_to_response(campaign: DocumentCampaign, summary: dict | None = None) -> CampaignResponse:
    summary = summary or {}
    status_value = campaign.status.value if hasattr(campaign.status, "value") else campaign.status
    return CampaignResponse(
        id=campaign.id,
        document_id=campaign.document_id,
        quiz_draft_id=campaign.quiz_draft_id,
        title=campaign.title,
        status=status_value,
        due_within_days=campaign.due_within_days,
        require_quiz=campaign.require_quiz,
        require_sign=campaign.require_sign,
        reminder_offsets_hours=campaign.reminder_offsets_hours or [],
        reminder_hours=list(campaign.reminder_offsets_hours or []),
        assigned_count=summary.get("total_assigned"),
        created_at=campaign.created_at,
        launched_at=campaign.launched_at,
        closed_at=campaign.closed_at,
        total_assigned=summary.get("total_assigned"),
        completed=summary.get("completed"),
        pending=summary.get("pending"),
        overdue=summary.get("overdue"),
        expired=summary.get("expired"),
        completion_rate=summary.get("completion_rate"),
    )


# =============================================================================
# Engineer Groups
# =============================================================================


@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupCreateRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Create a reusable engineer group for targeting campaigns."""
    service = DocumentCampaignService(db)
    group = await service.create_group(
        tenant_id=require_tenant_id(current_user.tenant_id),
        created_by_id=current_user.id,
        name=group_data.name,
        description=group_data.description,
        member_user_ids=group_data.member_user_ids,
    )
    return _group_to_response(group, member_count=len(group_data.member_user_ids))


@router.get("/groups", response_model=list[GroupResponse])
async def list_groups(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """List engineer groups with member counts (bare list for FE)."""
    service = DocumentCampaignService(db)
    rows = await service.list_groups(tenant_id=require_tenant_id(current_user.tenant_id))
    items = [_group_to_response(row["group"], row["member_count"]) for row in rows]
    return items


@router.post("/groups/{group_id}/members", response_model=GroupResponse)
async def add_group_members(
    group_id: int,
    members_data: GroupMembersRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Add members to an engineer group."""
    service = DocumentCampaignService(db)
    tenant_id = require_tenant_id(current_user.tenant_id)
    group = await service.add_group_members(
        tenant_id=tenant_id,
        group_id=group_id,
        user_ids=members_data.user_ids,
        added_by_id=current_user.id,
    )
    rows = await service.list_groups(tenant_id=tenant_id)
    member_count = next((row["member_count"] for row in rows if row["group"].id == group.id), 0)
    return _group_to_response(group, member_count)


@router.delete("/groups/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(
    group_id: int,
    user_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Remove a member from an engineer group."""
    service = DocumentCampaignService(db)
    await service.remove_group_member(
        tenant_id=require_tenant_id(current_user.tenant_id), group_id=group_id, user_id=user_id
    )


# =============================================================================
# Reminder defaults, compliance, evidence, question inbox (HSEC)
# =============================================================================


@router.get("/reminder-defaults", response_model=ReminderDefaultsResponse)
async def get_reminder_defaults(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Get tenant default reminder offsets (hours after launch) for new campaigns."""
    service = DocumentCampaignService(db)
    hours = await service.get_reminder_defaults(tenant_id=require_tenant_id(current_user.tenant_id))
    return ReminderDefaultsResponse(reminder_hours=hours)


@router.put("/reminder-defaults", response_model=ReminderDefaultsResponse)
async def set_reminder_defaults(
    body: ReminderDefaultsUpdateRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Set tenant default reminder offsets for new campaigns."""
    service = DocumentCampaignService(db)
    tenant_id = require_tenant_id(current_user.tenant_id)
    hours = await service.set_reminder_defaults(
        tenant_id=tenant_id,
        hours=body.reminder_hours,
        user_id=current_user.id,
    )
    return ReminderDefaultsResponse(reminder_hours=hours)


@router.get("/compliance", response_model=ComplianceSummaryResponse)
async def list_compliance_summary(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """List all campaigns with compliance summary metrics."""
    service = DocumentCampaignService(db)
    rows = await service.list_compliance_summary(tenant_id=require_tenant_id(current_user.tenant_id))
    items = [ComplianceSummaryItem(**row) for row in rows]
    return ComplianceSummaryResponse(items=items, total=len(items))


@router.get("/compliance/{campaign_id}/by-group", response_model=GroupComplianceResponse)
async def compliance_by_group(
    campaign_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Per-group compliance breakdown for campaigns with group audiences."""
    service = DocumentCampaignService(db)
    tenant_id = require_tenant_id(current_user.tenant_id)
    rows = await service.compliance_by_group(tenant_id=tenant_id, campaign_id=campaign_id)
    return GroupComplianceResponse(
        campaign_id=campaign_id,
        items=[GroupComplianceItem(**row) for row in rows],
        total=len(rows),
    )


@router.get("/campaigns/{campaign_id}/evidence-pack")
async def download_evidence_pack(
    campaign_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Export campaign completion evidence as JSON attachment."""
    service = DocumentCampaignService(db)
    pack = await service.build_evidence_pack(
        tenant_id=require_tenant_id(current_user.tenant_id),
        campaign_id=campaign_id,
    )
    filename = f"campaign-{campaign_id}-evidence.json"
    return JSONResponse(
        content=pack,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/question-inbox", response_model=QuestionInboxResponse)
async def list_question_inbox(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """List open assignee questions on documents with active or past campaigns."""
    service = DocumentCampaignService(db)
    rows = await service.list_question_inbox(tenant_id=require_tenant_id(current_user.tenant_id))
    items = [QuestionInboxItem(**row) for row in rows]
    return QuestionInboxResponse(items=items, total=len(items))


@router.post(
    "/assignments/{assignment_id}/questions",
    response_model=QuestionThreadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ask_assignment_question(
    assignment_id: int,
    body: AskAssignmentQuestionRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Assignee asks a question on the campaign document (creates discussion thread)."""
    service = DocumentCampaignService(db)
    thread = await service.ask_assignment_question(
        user_id=current_user.id,
        assignment_id=assignment_id,
        title=body.title,
        body=body.body,
    )
    status_value = thread.status.value if hasattr(thread.status, "value") else str(thread.status)
    return QuestionThreadResponse(
        id=thread.id,
        document_id=thread.document_id,
        title=thread.title,
        status=status_value,
        created_by_id=thread.created_by_id,
        created_at=thread.created_at,
    )


@router.post(
    "/questions/{thread_id}/reply",
    response_model=QuestionMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def reply_question(
    thread_id: int,
    body: QuestionReplyRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """HSEC/admin reply to an assignee question thread."""
    service = DocumentCampaignService(db)
    message = await service.reply_question(
        tenant_id=require_tenant_id(current_user.tenant_id),
        thread_id=thread_id,
        author_id=current_user.id,
        body=body.body,
    )
    return QuestionMessageResponse(
        id=message.id,
        thread_id=message.thread_id,
        author_id=message.author_id,
        body=message.body,
        created_at=message.created_at,
    )


@router.post("/questions/{thread_id}/resolve", response_model=QuestionThreadResponse)
async def resolve_question(
    thread_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Mark an assignee question thread as resolved."""
    service = DocumentCampaignService(db)
    thread = await service.resolve_question(
        tenant_id=require_tenant_id(current_user.tenant_id),
        thread_id=thread_id,
        resolver_id=current_user.id,
    )
    status_value = thread.status.value if hasattr(thread.status, "value") else str(thread.status)
    return QuestionThreadResponse(
        id=thread.id,
        document_id=thread.document_id,
        title=thread.title,
        status=status_value,
        created_by_id=thread.created_by_id,
        created_at=thread.created_at,
    )


# =============================================================================
# Campaigns
# =============================================================================


@router.post("/campaigns", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    campaign_data: CampaignCreateRequestFE,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Create a document campaign in draft status."""
    service = DocumentCampaignService(db)
    internal_data = campaign_data.to_internal()
    campaign = await service.create_campaign(
        tenant_id=require_tenant_id(current_user.tenant_id),
        created_by_id=current_user.id,
        document_id=internal_data.document_id,
        quiz_draft_id=internal_data.quiz_draft_id,
        title=internal_data.title,
        due_within_days=internal_data.due_within_days,
        require_quiz=internal_data.require_quiz,
        require_sign=internal_data.require_sign,
        reminder_offsets_hours=internal_data.reminder_offsets_hours,
        audience=internal_data.audience.model_dump(),
    )
    return _campaign_to_response(campaign)


@router.post("/campaigns/{campaign_id}/launch", response_model=LaunchCampaignResponse)
async def launch_campaign(
    campaign_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Expand audience, create assignments, and notify engineers."""
    service = DocumentCampaignService(db)
    result = await service.launch_campaign(
        tenant_id=require_tenant_id(current_user.tenant_id),
        campaign_id=campaign_id,
        launched_by_id=current_user.id,
    )
    return LaunchCampaignResponse(
        campaign_id=result["campaign_id"],
        assigned_count=result["assigned_count"],
        notified_count=result.get("notified_count", 0),
        id=result["campaign_id"],
        status=str(result.get("status", "active")),
        launched_at=result.get("launched_at"),
    )


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a campaign with its compliance summary."""
    service = DocumentCampaignService(db)
    data = await service.get_campaign_with_summary(
        tenant_id=require_tenant_id(current_user.tenant_id), campaign_id=campaign_id
    )
    campaign = data.pop("campaign")
    return _campaign_to_response(campaign, data)


@router.get("/documents/{document_id}/campaigns", response_model=list[CampaignResponse])
async def list_campaigns_for_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List campaigns for a document (bare list for FE #1146)."""
    service = DocumentCampaignService(db)
    tenant_id = require_tenant_id(current_user.tenant_id)
    campaigns = await service.list_campaigns_for_document(tenant_id=tenant_id, document_id=document_id)
    items = []
    for c in campaigns:
        data = await service.get_campaign_with_summary(tenant_id=tenant_id, campaign_id=c.id)
        data.pop("campaign", None)
        items.append(_campaign_to_response(c, data))
    return items


@router.get("/campaigns", response_model=CampaignListResponse)
async def list_campaigns(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Alias: list campaigns for a document (wrapped)."""
    service = DocumentCampaignService(db)
    campaigns = await service.list_campaigns_for_document(
        tenant_id=require_tenant_id(current_user.tenant_id), document_id=document_id
    )
    items = [_campaign_to_response(c) for c in campaigns]
    return CampaignListResponse(items=items, total=len(items))


# =============================================================================
# My Reading (Engineer-facing)
# =============================================================================


@router.get("/my-assignments", response_model=MyAssignmentsResponse)
async def get_my_assignments(
    db: DbSession,
    current_user: CurrentUser,
):
    """Get the current user's pending, overdue, and completed assignments."""
    service = DocumentCampaignService(db)
    rows = await service.get_my_assignments(
        tenant_id=require_tenant_id(current_user.tenant_id), user_id=current_user.id
    )

    items = []
    for row in rows:
        assignment = row["assignment"]
        campaign = row["campaign"]
        document = row["document"]
        status_value = assignment.status.value if hasattr(assignment.status, "value") else assignment.status
        items.append(
            AssignmentResponse(
                id=assignment.id,
                campaign_id=campaign.id,
                document_id=document.id,
                document_title=document.title,
                campaign_title=campaign.title,
                status=status_value,
                assigned_at=assignment.assigned_at,
                due_at=assignment.due_at,
                due_date=assignment.due_at,
                first_opened_at=assignment.first_opened_at,
                completed_at=assignment.completed_at,
                require_quiz=campaign.require_quiz,
                quiz_required=campaign.require_quiz,
                requires_quiz=campaign.require_quiz,
                require_sign=campaign.require_sign,
                quiz_score=assignment.quiz_score,
                quiz_passed=assignment.quiz_passed,
                quiz_attempts=assignment.quiz_attempts,
            )
        )

    return MyAssignmentsResponse(items=items, total=len(items))


@router.post("/assignments/{assignment_id}/open", response_model=AssignmentOpenedResponse)
async def open_assignment(
    assignment_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Record that the current user first opened their assignment."""
    service = DocumentCampaignService(db)
    assignment = await service.record_assignment_opened(user_id=current_user.id, assignment_id=assignment_id)
    return AssignmentOpenedResponse(message="Assignment opened recorded", first_opened_at=assignment.first_opened_at)


@router.get("/assignments/{assignment_id}/quiz", response_model=AssignmentQuizResponse)
async def get_assignment_quiz(
    assignment_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get quiz questions for the current user's assignment, without answer keys."""
    service = DocumentCampaignService(db)
    quiz = await service.get_assignment_quiz(user_id=current_user.id, assignment_id=assignment_id)
    return AssignmentQuizResponse(**quiz)


@router.post("/assignments/{assignment_id}/quiz", response_model=QuizSubmitResponse)
async def submit_assignment_quiz(
    assignment_id: int,
    submit_data: QuizSubmitRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Submit quiz answers; server grades MCQ and stores score/passed/attempts."""
    service = DocumentCampaignService(db)
    result = await service.submit_assignment_quiz(
        user_id=current_user.id,
        assignment_id=assignment_id,
        answers=[a.model_dump() for a in submit_data.answers],
    )
    return QuizSubmitResponse(score=result.score, passed=result.passed, pass_mark=result.pass_mark)


@router.post("/assignments/{assignment_id}/complete", response_model=CompleteAssignmentResponse)
async def complete_assignment(
    assignment_id: int,
    complete_data: CompleteAssignmentRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
):
    """Complete an assignment with acceptance statement and optional signature."""
    service = DocumentCampaignService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    assignment = await service.complete_assignment(
        user_id=current_user.id,
        assignment_id=assignment_id,
        acceptance_statement=complete_data.acceptance_statement,
        signature_data=complete_data.signature_data,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    status_value = assignment.status.value if hasattr(assignment.status, "value") else assignment.status
    return CompleteAssignmentResponse(id=assignment.id, status=status_value, completed_at=assignment.completed_at)


@router.post("/assignments/{assignment_id}/snooze", response_model=SnoozeAssignmentResponse)
async def snooze_assignment(
    assignment_id: int,
    snooze_data: SnoozeAssignmentRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Snooze reminders for the current user's pending/overdue assignment."""
    service = DocumentCampaignService(db)
    assignment = await service.snooze_assignment(
        user_id=current_user.id,
        assignment_id=assignment_id,
        hours=snooze_data.hours,
    )
    return SnoozeAssignmentResponse(id=assignment.id, snooze_until=assignment.snooze_until)
