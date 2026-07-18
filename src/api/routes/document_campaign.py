"""Document Campaign API Routes.

Engineer groups, document campaigns (read/quiz/sign-off), audience launch,
and the per-engineer assignment APIs (open, quiz, complete) used by "My Reading".
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from src.api.deps import CurrentUser, DbSession, require_permission
from src.api.schemas.document_campaign import (
    AssignmentOpenedResponse,
    AssignmentQuizResponse,
    AssignmentResponse,
    CampaignCreateRequest,
    CampaignCreateRequestFE,
    CampaignListResponse,
    CampaignResponse,
    CompleteAssignmentRequest,
    CompleteAssignmentResponse,
    GroupCreateRequest,
    GroupListResponse,
    GroupMembersRequest,
    GroupResponse,
    LaunchCampaignResponse,
    MyAssignmentsResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
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
        tenant_id=current_user.tenant_id,
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
    rows = await service.list_groups(tenant_id=current_user.tenant_id)
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
    group = await service.add_group_members(
        tenant_id=current_user.tenant_id,
        group_id=group_id,
        user_ids=members_data.user_ids,
        added_by_id=current_user.id,
    )
    rows = await service.list_groups(tenant_id=current_user.tenant_id)
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
    await service.remove_group_member(tenant_id=current_user.tenant_id, group_id=group_id, user_id=user_id)


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
    campaign_data = campaign_data.to_internal()
    campaign = await service.create_campaign(
        tenant_id=current_user.tenant_id,
        created_by_id=current_user.id,
        document_id=campaign_data.document_id,
        quiz_draft_id=campaign_data.quiz_draft_id,
        title=campaign_data.title,
        due_within_days=campaign_data.due_within_days,
        require_quiz=campaign_data.require_quiz,
        require_sign=campaign_data.require_sign,
        reminder_offsets_hours=campaign_data.reminder_offsets_hours,
        audience=campaign_data.audience.model_dump(),
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
        tenant_id=current_user.tenant_id,
        campaign_id=campaign_id,
        launched_by_id=current_user.id,
    )
    return LaunchCampaignResponse(
        campaign_id=result["campaign_id"],
        assigned_count=result["assigned_count"],
        notified_count=result.get("notified_count", 0),
        id=result["campaign_id"],
        status=result.get("status", "active"),
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
    data = await service.get_campaign_with_summary(tenant_id=current_user.tenant_id, campaign_id=campaign_id)
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
    campaigns = await service.list_campaigns_for_document(tenant_id=current_user.tenant_id, document_id=document_id)
    items = []
    for c in campaigns:
        data = await service.get_campaign_with_summary(tenant_id=current_user.tenant_id, campaign_id=c.id)
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
    campaigns = await service.list_campaigns_for_document(tenant_id=current_user.tenant_id, document_id=document_id)
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
    rows = await service.get_my_assignments(tenant_id=current_user.tenant_id, user_id=current_user.id)

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
