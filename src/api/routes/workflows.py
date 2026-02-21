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

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from src.api.dependencies import CurrentUser, DbSession
from src.domain.services import workflow_engine as engine

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


@router.get("/templates")
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


@router.get("/templates/{template_code}")
async def get_workflow_template(
    template_code: str, db: DbSession, current_user: CurrentUser
):
    """Get workflow template details."""
    t = await engine.get_template(db, template_code)
    if t is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )
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


@router.post("/start")
async def start_workflow(
    request: WorkflowStartRequest, db: DbSession, current_user: CurrentUser
):
    """Start a new workflow instance."""
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

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


@router.get("/instances")
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

    items = []
    for inst in instances:
        steps = await engine.get_instance_steps(db, inst.id)
        total_steps = len(steps)
        completed_steps = sum(1 for s in steps if s.status == "completed")
        progress = int((completed_steps / total_steps) * 100) if total_steps else 0

        now = datetime.utcnow()
        sla_status = "ok"
        if inst.sla_due_at:
            if now > inst.sla_due_at:
                sla_status = "breached"
            elif inst.sla_warning_at and now > inst.sla_warning_at:
                sla_status = "warning"

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


@router.get("/instances/{workflow_id}")
async def get_workflow_instance(
    workflow_id: int, db: DbSession, current_user: CurrentUser
):
    """Get workflow instance details with all steps."""
    inst = await engine.get_instance(db, workflow_id)
    if inst is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow instance not found"
        )

    steps = await engine.get_instance_steps(db, workflow_id)
    total_steps = len(steps)
    completed_steps = sum(1 for s in steps if s.status == "completed")
    progress = int((completed_steps / total_steps) * 100) if total_steps else 0

    now = datetime.utcnow()
    sla_status = "ok"
    if inst.sla_due_at:
        if now > inst.sla_due_at:
            sla_status = "breached"
        elif inst.sla_warning_at and now > inst.sla_warning_at:
            sla_status = "warning"

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
        "total_steps": total_steps,
        "progress": progress,
        "sla_due_at": inst.sla_due_at.isoformat() if inst.sla_due_at else None,
        "sla_status": sla_status,
        "initiated_by": inst.initiated_by,
        "started_at": inst.started_at.isoformat() if inst.started_at else None,
        "completed_at": inst.completed_at.isoformat() if inst.completed_at else None,
        "context": inst.context,
        "steps": step_data,
    }


@router.post("/instances/{workflow_id}/advance")
async def advance_workflow(
    workflow_id: int,
    db: DbSession,
    current_user: CurrentUser,
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result


@router.post("/instances/{workflow_id}/cancel")
async def cancel_workflow(
    workflow_id: int,
    db: DbSession,
    current_user: CurrentUser,
    reason: Optional[str] = Query(None),
):
    """Cancel a workflow instance."""
    try:
        inst = await engine.cancel_workflow(db, workflow_id, current_user.id, reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {
        "workflow_id": inst.id,
        "status": inst.status,
        "cancelled_by": current_user.id,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# APPROVAL ENDPOINTS
# ============================================================================


@router.get("/approvals/pending")
async def get_pending_approvals(db: DbSession, current_user: CurrentUser):
    """Get pending approvals for current user."""
    approvals = await engine.get_pending_approvals(db, current_user.id)
    return {"approvals": approvals, "total": len(approvals)}


@router.post("/approvals/{step_id}/approve")
async def approve_request(
    step_id: int, response: ApprovalResponse, db: DbSession, current_user: CurrentUser
):
    """Approve a workflow step."""
    try:
        result = await engine.approve_step(
            db, step_id, current_user.id, response.effective_notes
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result


@router.post("/approvals/{step_id}/reject")
async def reject_request(
    step_id: int, response: ApprovalResponse, db: DbSession, current_user: CurrentUser
):
    """Reject a workflow step."""
    if not response.reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason required for rejection",
        )
    try:
        result = await engine.reject_step(db, step_id, current_user.id, response.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result


@router.post("/approvals/bulk-approve")
async def bulk_approve_requests(
    request: BulkApprovalRequest, db: DbSession, current_user: CurrentUser
):
    """Bulk approve multiple workflow steps."""
    result = await engine.bulk_approve(
        db, request.approval_ids, current_user.id, request.notes
    )
    return result


# ============================================================================
# ESCALATION ENDPOINTS
# ============================================================================


@router.get("/escalations/pending")
async def get_pending_escalations(db: DbSession, current_user: CurrentUser):
    """Get workflows pending escalation."""
    escalations = await engine.check_escalations(db)
    return {"escalations": escalations, "total": len(escalations)}


@router.post("/instances/{workflow_id}/escalate")
async def escalate_workflow(
    workflow_id: int,
    request: EscalationRequest,
    db: DbSession,
    current_user: CurrentUser,
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result


# ============================================================================
# DELEGATION ENDPOINTS
# ============================================================================


@router.get("/delegations")
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


@router.post("/delegations")
async def create_delegation(
    request: DelegationRequest, db: DbSession, current_user: CurrentUser
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


@router.delete("/delegations/{delegation_id}")
async def cancel_delegation(
    delegation_id: int, db: DbSession, current_user: CurrentUser
):
    """Cancel a delegation."""
    success = await engine.cancel_delegation(db, delegation_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Delegation not found"
        )
    return {
        "delegation_id": delegation_id,
        "status": "cancelled",
        "cancelled_at": datetime.utcnow().isoformat(),
    }


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================


@router.get("/stats")
async def get_workflow_stats(db: DbSession, current_user: CurrentUser):
    """Get live workflow statistics from the database."""
    return await engine.get_workflow_stats(db)
