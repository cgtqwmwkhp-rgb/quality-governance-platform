"""
Workflow API Routes — DB-backed persistence

Features:
- Workflow template management
- Workflow instance lifecycle (start, advance, cancel)
- Approval management (approve, reject, bulk)
- Escalation
- Delegation configuration
- Live statistics
"""

from datetime import datetime, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession, require_permission
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.workflows import (
    AdvanceWorkflowResponse,
    ApproveStepResponse,
    BulkApproveResponse,
    CancelDelegationResponse,
    CancelWorkflowResponse,
    CreateDelegationResponse,
    EscalateWorkflowResponse,
    GetInstanceResponse,
    GetTemplateResponse,
    GetWorkflowStatsResponse,
    ListDelegationsResponse,
    ListInstancesResponse,
    ListPendingApprovalsResponse,
    ListPendingEscalationsResponse,
    ListTemplatesResponse,
    RejectStepResponse,
    StartWorkflowResponse,
)
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.user import User
from src.domain.services import workflow_engine as engine
from src.domain.services.workflow_calculation_service import WorkflowCalculationService
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


# ============================================================================
# SCHEMAS
# ============================================================================


class WorkflowStartRequest(BaseModel):
    template_code: str
    entity_type: str
    entity_id: str
    context: Optional[dict] = None
    priority: str = "normal"


class ApprovalResponse(BaseModel):
    notes: Optional[str] = None
    comments: Optional[str] = None
    reason: Optional[str] = None

    @property
    def effective_notes(self) -> Optional[str]:
        return self.notes or self.comments


class BulkApprovalRequest(BaseModel):
    approval_ids: List[int]
    notes: Optional[str] = None


class DelegationRequest(BaseModel):
    delegate_id: int
    start_date: datetime
    end_date: datetime
    reason: Optional[str] = None
    workflow_types: Optional[List[str]] = None


class EscalationRequest(BaseModel):
    escalate_to: int
    reason: str
    new_priority: Optional[str] = None


# ============================================================================
# TEMPLATE ENDPOINTS
# ============================================================================


@router.get("/templates", response_model=ListTemplatesResponse)
async def list_workflow_templates(db: DbSession, current_user: CurrentUser):
    """List available workflow templates, seeding defaults if empty."""
    await engine.seed_default_templates(db)
    templates = await engine.list_templates(db)
    return {
        "templates": [
            {
                "code": t.code,
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "trigger_entity_type": t.trigger_entity_type,
                "sla_hours": t.sla_hours,
                "steps_count": len(t.steps) if t.steps else 0,
            }
            for t in templates
        ]
    }


@router.get("/templates/{template_code}", response_model=GetTemplateResponse)
async def get_workflow_template(template_code: str, db: DbSession, current_user: CurrentUser):
    """Get workflow template details."""
    t = await engine.get_template(db, template_code)
    if t is None:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return {
        "id": t.id,
        "code": t.code,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "trigger_entity_type": t.trigger_entity_type,
        "trigger_conditions": t.trigger_conditions,
        "sla_hours": t.sla_hours,
        "warning_hours": t.warning_hours,
        "steps": t.steps,
        "escalation_rules": t.escalation_rules,
        "is_active": t.is_active,
        "version": t.version,
    }


# ============================================================================
# WORKFLOW INSTANCE ENDPOINTS
# ============================================================================


@router.post("/start", response_model=StartWorkflowResponse)
async def start_workflow(
    request: WorkflowStartRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("workflow:execute"))],
):
    """Start a new workflow instance."""
    _span = tracer.start_span("start_workflow") if tracer else None
    if _span:
        _span.set_attribute("template_code", request.template_code)
    try:
        instance = await engine.start_workflow(
            db,
            template_code=request.template_code,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            initiated_by=current_user.id,
            context=request.context,
            priority=request.priority,
        )
    except ValueError as exc:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)

    track_metric("workflow.started", 1, {"template": request.template_code})
    if _span:
        _span.end()
    steps = await engine.get_instance_steps(db, instance.id)
    return {
        "id": instance.id,
        "template_id": instance.template_id,
        "entity_type": instance.entity_type,
        "entity_id": instance.entity_id,
        "status": instance.status,
        "priority": instance.priority,
        "current_step": instance.current_step,
        "current_step_name": instance.current_step_name,
        "total_steps": len(steps),
        "sla_due_at": instance.sla_due_at.isoformat() if instance.sla_due_at else None,
        "started_at": instance.started_at.isoformat() if instance.started_at else None,
    }


@router.get("/instances", response_model=ListInstancesResponse)
async def list_workflow_instances(
    db: DbSession,
    current_user: CurrentUser,
    status: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """List workflow instances with filtering and pagination."""
    instances, total = await engine.list_instances(
        db,
        status=status,
        entity_type=entity_type,
        page=page,
        page_size=page_size,
    )

    now = datetime.now(timezone.utc)
    items = []
    for inst in instances:
        steps = await engine.get_instance_steps(db, inst.id)
        progress = WorkflowCalculationService.calculate_progress(steps)
        sla_status = WorkflowCalculationService.calculate_sla_status(inst, now)

        items.append(
            {
                "id": inst.id,
                "template_id": inst.template_id,
                "entity_type": inst.entity_type,
                "entity_id": inst.entity_id,
                "status": inst.status,
                "priority": inst.priority,
                "current_step": inst.current_step_name or "",
                "progress": progress,
                "sla_status": sla_status,
                "started_at": inst.started_at.isoformat() if inst.started_at else None,
            }
        )

    return {"items": items, "total": total}


@router.get("/instances/{workflow_id}", response_model=GetInstanceResponse)
async def get_workflow_instance(workflow_id: int, db: DbSession, current_user: CurrentUser):
    """Get workflow instance details with all steps."""
    inst = await engine.get_instance(db, workflow_id)
    if inst is None:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)

    steps = await engine.get_instance_steps(db, workflow_id)
    progress = WorkflowCalculationService.calculate_progress(steps)
    sla_status = WorkflowCalculationService.calculate_sla_status(inst)

    step_data = []
    for s in steps:
        step_data.append(
            {
                "id": s.id,
                "step_number": s.step_number,
                "name": s.step_name,
                "type": s.step_type,
                "status": s.status,
                "approval_type": s.approval_type,
                "required_approvers": s.required_approvers,
                "outcome": s.outcome,
                "outcome_reason": s.outcome_reason,
                "outcome_by": s.outcome_by,
                "due_at": s.due_at.isoformat() if s.due_at else None,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
        )

    return {
        "id": inst.id,
        "template_id": inst.template_id,
        "entity_type": inst.entity_type,
        "entity_id": inst.entity_id,
        "status": inst.status,
        "priority": inst.priority,
        "current_step": inst.current_step,
        "current_step_name": inst.current_step_name,
        "total_steps": len(steps),
        "progress": progress,
        "sla_due_at": inst.sla_due_at.isoformat() if inst.sla_due_at else None,
        "sla_status": sla_status,
        "initiated_by": inst.initiated_by,
        "started_at": inst.started_at.isoformat() if inst.started_at else None,
        "completed_at": inst.completed_at.isoformat() if inst.completed_at else None,
        "context": inst.context,
        "steps": step_data,
    }


@router.post("/instances/{workflow_id}/advance", response_model=AdvanceWorkflowResponse)
async def advance_workflow(
    workflow_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("workflow:execute"))],
    outcome: str = Query(...),
    notes: Optional[str] = Query(None),
):
    """Advance workflow to next step."""
    try:
        result = await engine.advance_workflow(
            db,
            instance_id=workflow_id,
            outcome=outcome,
            outcome_by=current_user.id,
            notes=notes,
        )
    except ValueError as exc:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    return result


@router.post("/instances/{workflow_id}/cancel", response_model=CancelWorkflowResponse)
async def cancel_workflow(
    workflow_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("workflow:execute"))],
    reason: Optional[str] = Query(None),
):
    """Cancel a workflow instance."""
    try:
        inst = await engine.cancel_workflow(db, workflow_id, current_user.id, reason)
    except ValueError as exc:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    return {
        "workflow_id": inst.id,
        "status": inst.status,
        "cancelled_by": current_user.id,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# APPROVAL ENDPOINTS
# ============================================================================


@router.get("/approvals/pending", response_model=ListPendingApprovalsResponse)
async def get_pending_approvals(db: DbSession, current_user: CurrentUser):
    """Get pending approvals for current user."""
    approvals = await engine.get_pending_approvals(db, current_user.id)
    return {"approvals": approvals, "total": len(approvals)}


@router.post("/approvals/{step_id}/approve", response_model=ApproveStepResponse)
async def approve_request(
    step_id: int,
    response: ApprovalResponse,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("workflow:execute"))],
):
    """Approve a workflow step."""
    try:
        result = await engine.approve_step(db, step_id, current_user.id, response.effective_notes)
    except ValueError as exc:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    return result


@router.post("/approvals/{step_id}/reject", response_model=RejectStepResponse)
async def reject_request(
    step_id: int,
    response: ApprovalResponse,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("workflow:execute"))],
):
    """Reject a workflow step."""
    if not response.reason:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    try:
        result = await engine.reject_step(db, step_id, current_user.id, response.reason)
    except ValueError as exc:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    return result


@router.post("/approvals/bulk-approve", response_model=BulkApproveResponse)
async def bulk_approve_requests(
    request: BulkApprovalRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("workflow:execute"))],
):
    """Bulk approve multiple workflow steps."""
    result = await engine.bulk_approve(db, request.approval_ids, current_user.id, request.notes)
    return result


# ============================================================================
# ESCALATION ENDPOINTS
# ============================================================================


@router.get("/escalations/pending", response_model=ListPendingEscalationsResponse)
async def get_pending_escalations(db: DbSession, current_user: CurrentUser):
    """Get workflows pending escalation."""
    escalations = await engine.check_escalations(db)
    return {"escalations": escalations, "total": len(escalations)}


@router.post("/instances/{workflow_id}/escalate", response_model=EscalateWorkflowResponse)
async def escalate_workflow(
    workflow_id: int,
    request: EscalationRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("workflow:execute"))],
):
    """Escalate a workflow."""
    try:
        result = await engine.escalate_workflow(
            db,
            instance_id=workflow_id,
            escalated_by=current_user.id,
            reason=request.reason,
            new_priority=request.new_priority,
        )
    except ValueError as exc:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    return result


# ============================================================================
# DELEGATION ENDPOINTS
# ============================================================================


@router.get("/delegations", response_model=ListDelegationsResponse)
async def get_my_delegations(db: DbSession, current_user: CurrentUser):
    """Get current user's delegations."""
    delegations = await engine.get_active_delegations(db, current_user.id)
    return {
        "delegations": [
            {
                "id": d.id,
                "delegate_id": d.delegate_id,
                "start_date": d.start_date.isoformat() if d.start_date else None,
                "end_date": d.end_date.isoformat() if d.end_date else None,
                "reason": d.reason,
                "is_active": d.is_active,
            }
            for d in delegations
        ]
    }


@router.post("/delegations", response_model=CreateDelegationResponse)
async def create_delegation(
    request: DelegationRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("workflow:create"))],
):
    """Set up out-of-office delegation."""
    d = await engine.set_delegation(
        db,
        user_id=current_user.id,
        delegate_id=request.delegate_id,
        start_date=request.start_date,
        end_date=request.end_date,
        reason=request.reason,
        workflow_types=request.workflow_types,
    )
    return {
        "id": d.id,
        "user_id": d.user_id,
        "delegate_id": d.delegate_id,
        "start_date": d.start_date.isoformat(),
        "end_date": d.end_date.isoformat(),
        "reason": d.reason,
        "status": "active",
    }


@router.delete("/delegations/{delegation_id}", response_model=CancelDelegationResponse)
async def cancel_delegation(delegation_id: int, db: DbSession, current_user: CurrentSuperuser):
    """Cancel a delegation."""
    success = await engine.cancel_delegation(db, delegation_id)
    if not success:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return {
        "delegation_id": delegation_id,
        "status": "cancelled",
        "cancelled_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================


@router.get("/stats", response_model=GetWorkflowStatsResponse)
async def get_workflow_stats(db: DbSession, current_user: CurrentUser):
    """Get live workflow statistics from the database."""
    return await engine.get_workflow_stats(db)
