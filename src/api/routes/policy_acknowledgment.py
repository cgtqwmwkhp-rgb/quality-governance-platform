"""Policy Acknowledgment API Routes.

Provides endpoints for managing policy acknowledgment requirements,
tracking user acknowledgments, and compliance reporting.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.schemas.policy_acknowledgment import (
    AcknowledgmentRequirementCreate,
    AcknowledgmentRequirementResponse,
    AssignAcknowledgmentRequest,
    ComplianceDashboardResponse,
    DocumentReadLogListResponse,
    DocumentReadLogResponse,
    LogDocumentReadRequest,
    PolicyAcknowledgmentListResponse,
    PolicyAcknowledgmentResponse,
    PolicyAcknowledgmentStatusResponse,
    RecordAcknowledgmentRequest,
)
from src.domain.models.policy_acknowledgment import (
    AcknowledgmentStatus,
    PolicyAcknowledgment,
    PolicyAcknowledgmentRequirement,
)
from src.services.policy_acknowledgment import (
    DocumentReadLogService,
    PolicyAcknowledgmentService,
)

router = APIRouter(prefix="/policy-acknowledgments", tags=["Policy Acknowledgments"])


# =============================================================================
# Acknowledgment Requirements
# =============================================================================

@router.post("/requirements", response_model=AcknowledgmentRequirementResponse, status_code=status.HTTP_201_CREATED)
async def create_acknowledgment_requirement(
    requirement_data: AcknowledgmentRequirementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create an acknowledgment requirement for a policy."""
    service = PolicyAcknowledgmentService(db)
    requirement = await service.create_requirement(
        policy_id=requirement_data.policy_id,
        acknowledgment_type=requirement_data.acknowledgment_type,
        required_for_all=requirement_data.required_for_all,
        required_departments=requirement_data.required_departments,
        required_roles=requirement_data.required_roles,
        required_user_ids=requirement_data.required_user_ids,
        due_within_days=requirement_data.due_within_days,
        reminder_days_before=requirement_data.reminder_days_before,
        quiz_questions=requirement_data.quiz_questions,
        quiz_passing_score=requirement_data.quiz_passing_score,
    )
    return AcknowledgmentRequirementResponse.from_orm(requirement)


@router.get("/requirements/{requirement_id}", response_model=AcknowledgmentRequirementResponse)
async def get_acknowledgment_requirement(
    requirement_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get an acknowledgment requirement."""
    result = await db.execute(
        select(PolicyAcknowledgmentRequirement)
        .where(PolicyAcknowledgmentRequirement.id == requirement_id)
    )
    requirement = result.scalar_one_or_none()
    
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")
    
    return AcknowledgmentRequirementResponse.from_orm(requirement)


@router.post("/requirements/{requirement_id}/assign", response_model=PolicyAcknowledgmentListResponse)
async def assign_acknowledgments(
    requirement_id: int,
    assign_data: AssignAcknowledgmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Assign acknowledgment tasks to users."""
    service = PolicyAcknowledgmentService(db)
    
    try:
        acknowledgments = await service.assign_acknowledgments(
            requirement_id=requirement_id,
            user_ids=assign_data.user_ids,
            policy_version=assign_data.policy_version,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return PolicyAcknowledgmentListResponse(
        items=[PolicyAcknowledgmentResponse.from_orm(a) for a in acknowledgments],
        total=len(acknowledgments),
    )


# =============================================================================
# User Acknowledgments
# =============================================================================

@router.get("/my-pending", response_model=PolicyAcknowledgmentListResponse)
async def get_my_pending_acknowledgments(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get current user's pending acknowledgments."""
    service = PolicyAcknowledgmentService(db)
    pending = await service.get_user_pending_acknowledgments(current_user.get("id"))
    
    return PolicyAcknowledgmentListResponse(
        items=[PolicyAcknowledgmentResponse.from_orm(a) for a in pending],
        total=len(pending),
    )


@router.get("/{acknowledgment_id}", response_model=PolicyAcknowledgmentResponse)
async def get_acknowledgment(
    acknowledgment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a specific acknowledgment."""
    result = await db.execute(
        select(PolicyAcknowledgment).where(PolicyAcknowledgment.id == acknowledgment_id)
    )
    ack = result.scalar_one_or_none()
    
    if not ack:
        raise HTTPException(status_code=404, detail="Acknowledgment not found")
    
    return PolicyAcknowledgmentResponse.from_orm(ack)


@router.post("/{acknowledgment_id}/open")
async def record_policy_opened(
    acknowledgment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Record that a user has opened a policy for reading."""
    service = PolicyAcknowledgmentService(db)
    ack = await service.record_policy_opened(acknowledgment_id)
    
    if not ack:
        raise HTTPException(status_code=404, detail="Acknowledgment not found")
    
    return {"message": "Policy opened recorded", "first_opened_at": ack.first_opened_at}


@router.post("/{acknowledgment_id}/reading-time")
async def update_reading_time(
    acknowledgment_id: int,
    additional_seconds: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update reading time for an acknowledgment."""
    service = PolicyAcknowledgmentService(db)
    ack = await service.update_reading_time(acknowledgment_id, additional_seconds)
    
    if not ack:
        raise HTTPException(status_code=404, detail="Acknowledgment not found")
    
    return {"message": "Reading time updated", "total_seconds": ack.time_spent_seconds}


@router.post("/{acknowledgment_id}/acknowledge", response_model=PolicyAcknowledgmentResponse)
async def record_acknowledgment(
    acknowledgment_id: int,
    ack_data: RecordAcknowledgmentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Record a user's acknowledgment of a policy."""
    service = PolicyAcknowledgmentService(db)
    
    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    try:
        ack = await service.record_acknowledgment(
            acknowledgment_id=acknowledgment_id,
            quiz_score=ack_data.quiz_score,
            acceptance_statement=ack_data.acceptance_statement,
            signature_data=ack_data.signature_data,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return PolicyAcknowledgmentResponse.from_orm(ack)


# =============================================================================
# Policy Status
# =============================================================================

@router.get("/policies/{policy_id}/status", response_model=PolicyAcknowledgmentStatusResponse)
async def get_policy_acknowledgment_status(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get acknowledgment status summary for a policy."""
    service = PolicyAcknowledgmentService(db)
    status = await service.get_policy_acknowledgment_status(policy_id)
    return PolicyAcknowledgmentStatusResponse(**status)


# =============================================================================
# Compliance Dashboard
# =============================================================================

@router.get("/dashboard", response_model=ComplianceDashboardResponse)
async def get_compliance_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get overall policy acknowledgment compliance dashboard."""
    service = PolicyAcknowledgmentService(db)
    dashboard = await service.get_compliance_dashboard()
    return ComplianceDashboardResponse(**dashboard)


@router.post("/check-overdue")
async def check_overdue_acknowledgments(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Check for and mark overdue acknowledgments."""
    service = PolicyAcknowledgmentService(db)
    overdue = await service.check_overdue_acknowledgments()
    
    return {
        "message": "Overdue check completed",
        "newly_overdue": len(overdue),
    }


@router.get("/reminders-needed")
async def get_reminders_needed(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get acknowledgments that need reminder emails."""
    service = PolicyAcknowledgmentService(db)
    reminders = await service.get_reminders_to_send()
    
    return {
        "reminders_needed": len(reminders),
        "details": reminders,
    }


# =============================================================================
# Document Read Logs
# =============================================================================

@router.post("/read-logs", response_model=DocumentReadLogResponse)
async def log_document_read(
    log_data: LogDocumentReadRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Log a document read/access."""
    service = DocumentReadLogService(db)
    
    ip_address = request.client.host if request.client else None
    
    log = await service.log_document_access(
        document_type=log_data.document_type,
        document_id=log_data.document_id,
        user_id=current_user.get("id"),
        document_version=log_data.document_version,
        duration_seconds=log_data.duration_seconds,
        scroll_percentage=log_data.scroll_percentage,
        ip_address=ip_address,
        device_type=log_data.device_type,
    )
    
    return DocumentReadLogResponse.from_orm(log)


@router.get("/read-logs/document/{document_type}/{document_id}", response_model=DocumentReadLogListResponse)
async def get_document_read_history(
    document_type: str,
    document_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get read history for a document."""
    service = DocumentReadLogService(db)
    logs = await service.get_document_read_history(document_type, document_id, limit)
    
    return DocumentReadLogListResponse(
        items=[DocumentReadLogResponse.from_orm(l) for l in logs],
        total=len(logs),
    )


@router.get("/read-logs/user/{user_id}", response_model=DocumentReadLogListResponse)
async def get_user_read_history(
    user_id: int,
    document_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get read history for a user."""
    service = DocumentReadLogService(db)
    logs = await service.get_user_read_history(user_id, document_type, limit)
    
    return DocumentReadLogListResponse(
        items=[DocumentReadLogResponse.from_orm(l) for l in logs],
        total=len(logs),
    )
