"""
Workflow API Routes

Features:
- Workflow template management
- Workflow instance operations
- Approval management
- Delegation configuration
- Bulk actions
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.dependencies import CurrentUser
from src.domain.services.workflow_engine import workflow_engine

router = APIRouter()


# ============================================================================
# SCHEMAS
# ============================================================================


class WorkflowStartRequest(BaseModel):
    """Request to start a workflow"""

    template_code: str
    entity_type: str
    entity_id: str
    context: Optional[dict] = None
    priority: str = "normal"


class ApprovalResponse(BaseModel):
    """Approval/Rejection response"""

    notes: Optional[str] = None
    reason: Optional[str] = None


class BulkApprovalRequest(BaseModel):
    """Bulk approval request"""

    approval_ids: List[str]
    notes: Optional[str] = None


class DelegationRequest(BaseModel):
    """Set delegation request"""

    delegate_id: int
    start_date: datetime
    end_date: datetime
    reason: Optional[str] = None
    workflow_types: Optional[List[str]] = None


class EscalationRequest(BaseModel):
    """Escalation request"""

    escalate_to: int
    reason: str
    new_priority: Optional[str] = None


# ============================================================================
# TEMPLATE ENDPOINTS
# ============================================================================


@router.get("/templates")
async def list_workflow_templates(current_user: CurrentUser):
    """List available workflow templates."""
    templates = []
    for code, template in workflow_engine.templates.items():
        templates.append(
            {
                "code": code,
                "name": template["name"],
                "description": template["description"],
                "category": template["category"],
                "trigger_entity_type": template["trigger_entity_type"],
                "sla_hours": template.get("sla_hours"),
                "steps_count": len(template["steps"]),
            }
        )
    return {"templates": templates}


@router.get("/templates/{template_code}")
async def get_workflow_template(template_code: str, current_user: CurrentUser):
    """Get workflow template details."""
    template = workflow_engine.templates.get(template_code)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


# ============================================================================
# WORKFLOW INSTANCE ENDPOINTS
# ============================================================================


@router.post("/start")
async def start_workflow(request: WorkflowStartRequest, current_user: CurrentUser):
    """Start a new workflow instance."""
    result = workflow_engine.start_workflow(
        template_code=request.template_code,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        initiated_by=current_user.id,
        context=request.context,
        priority=request.priority,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/instances")
async def list_workflow_instances(
    current_user: CurrentUser,
    status: Optional[str] = None,
    entity_type: Optional[str] = None,
):
    """List workflow instances."""
    # Mock data
    instances = [
        {
            "id": "WF-20260119001",
            "template_code": "RIDDOR",
            "template_name": "RIDDOR Reporting",
            "entity_type": "incident",
            "entity_id": "INC-2026-0042",
            "status": "awaiting_approval",
            "priority": "high",
            "current_step": "Management Sign-off",
            "progress": 75,
            "sla_status": "warning",
            "started_at": "2026-01-19T08:00:00Z",
        },
        {
            "id": "WF-20260118002",
            "template_code": "CAPA",
            "template_name": "Corrective/Preventive Action",
            "entity_type": "action",
            "entity_id": "ACT-2026-0105",
            "status": "in_progress",
            "priority": "normal",
            "current_step": "Implementation",
            "progress": 50,
            "sla_status": "ok",
            "started_at": "2026-01-18T10:00:00Z",
        },
    ]

    if status:
        instances = [i for i in instances if i["status"] == status]
    if entity_type:
        instances = [i for i in instances if i["entity_type"] == entity_type]

    return {"instances": instances, "total": len(instances)}


@router.get("/instances/{workflow_id}")
async def get_workflow_instance(workflow_id: str, current_user: CurrentUser):
    """Get workflow instance details."""
    # Mock data
    return {
        "id": workflow_id,
        "template_code": "RIDDOR",
        "template_name": "RIDDOR Reporting",
        "entity_type": "incident",
        "entity_id": "INC-2026-0042",
        "entity_title": "Slip and fall incident - Site A",
        "status": "awaiting_approval",
        "priority": "high",
        "current_step": 2,
        "current_step_name": "Management Sign-off",
        "total_steps": 4,
        "progress": 75,
        "sla_due_at": "2026-01-20T08:00:00Z",
        "sla_status": "warning",
        "initiated_by": {"id": 1, "name": "John Doe"},
        "started_at": "2026-01-19T08:00:00Z",
        "steps": [
            {
                "step_number": 0,
                "name": "Initial Review",
                "type": "approval",
                "status": "completed",
                "outcome": "approved",
                "completed_at": "2026-01-19T09:30:00Z",
                "completed_by": {"id": 2, "name": "Safety Manager"},
            },
            {
                "step_number": 1,
                "name": "HSE Notification",
                "type": "task",
                "status": "completed",
                "outcome": "completed",
                "completed_at": "2026-01-19T14:00:00Z",
                "completed_by": {"id": 2, "name": "Safety Manager"},
            },
            {
                "step_number": 2,
                "name": "Management Sign-off",
                "type": "approval",
                "status": "pending",
                "approvers": [{"id": 3, "name": "Operations Director"}],
                "due_at": "2026-01-19T18:00:00Z",
            },
            {
                "step_number": 3,
                "name": "Final Submission",
                "type": "task",
                "status": "pending",
            },
        ],
        "history": [
            {
                "action": "workflow_started",
                "user": "John Doe",
                "timestamp": "2026-01-19T08:00:00Z",
            },
            {
                "action": "step_completed",
                "step": "Initial Review",
                "outcome": "approved",
                "user": "Safety Manager",
                "timestamp": "2026-01-19T09:30:00Z",
            },
            {
                "action": "step_completed",
                "step": "HSE Notification",
                "outcome": "completed",
                "user": "Safety Manager",
                "timestamp": "2026-01-19T14:00:00Z",
            },
        ],
    }


@router.post("/instances/{workflow_id}/advance")
async def advance_workflow(
    workflow_id: str,
    outcome: str,
    current_user: CurrentUser,
    notes: Optional[str] = None,
):
    """Advance workflow to next step."""
    result = workflow_engine.advance_workflow(
        workflow_id=workflow_id,
        outcome=outcome,
        outcome_by=current_user.id,
        notes=notes,
    )
    return result


@router.post("/instances/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str, current_user: CurrentUser, reason: Optional[str] = None):
    """Cancel a workflow instance."""
    return {
        "workflow_id": workflow_id,
        "status": "cancelled",
        "cancelled_by": current_user.id,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# APPROVAL ENDPOINTS
# ============================================================================


@router.get("/approvals/pending")
async def get_pending_approvals(current_user: CurrentUser):
    """Get pending approvals for current user."""
    approvals = workflow_engine.get_pending_approvals(current_user.id)
    return {"approvals": approvals, "total": len(approvals)}


@router.post("/approvals/{approval_id}/approve")
async def approve_request(approval_id: str, current_user: CurrentUser, response: ApprovalResponse):
    """Approve an approval request."""
    result = workflow_engine.approve(
        approval_id=approval_id,
        user_id=current_user.id,
        notes=response.notes,
    )
    return result


@router.post("/approvals/{approval_id}/reject")
async def reject_request(approval_id: str, current_user: CurrentUser, response: ApprovalResponse):
    """Reject an approval request."""
    if not response.reason:
        raise HTTPException(status_code=400, detail="Reason required for rejection")

    result = workflow_engine.reject(
        approval_id=approval_id,
        user_id=current_user.id,
        reason=response.reason,
    )
    return result


@router.post("/approvals/bulk-approve")
async def bulk_approve_requests(request: BulkApprovalRequest, current_user: CurrentUser):
    """Bulk approve multiple requests."""
    result = workflow_engine.bulk_approve(
        approval_ids=request.approval_ids,
        user_id=current_user.id,
        notes=request.notes,
    )
    return result


# ============================================================================
# ESCALATION ENDPOINTS
# ============================================================================


@router.get("/escalations/pending")
async def get_pending_escalations(current_user: CurrentUser):
    """Get workflows pending escalation."""
    escalations = workflow_engine.check_escalations()
    return {"escalations": escalations, "total": len(escalations)}


@router.post("/instances/{workflow_id}/escalate")
async def escalate_workflow(workflow_id: str, request: EscalationRequest, current_user: CurrentUser):
    """Escalate a workflow."""
    result = workflow_engine.escalate(
        workflow_id=workflow_id,
        escalate_to=request.escalate_to,
        reason=request.reason,
        new_priority=request.new_priority,
    )
    return result


# ============================================================================
# DELEGATION ENDPOINTS
# ============================================================================


@router.get("/delegations")
async def get_my_delegations(current_user: CurrentUser):
    """Get current user's delegations."""
    delegations = workflow_engine.get_active_delegations(current_user.id)
    return {"delegations": delegations}


@router.post("/delegations")
async def set_delegation(request: DelegationRequest, current_user: CurrentUser):
    """Set up out-of-office delegation."""
    result = workflow_engine.set_delegation(
        user_id=current_user.id,
        delegate_id=request.delegate_id,
        start_date=request.start_date,
        end_date=request.end_date,
        reason=request.reason,
        workflow_types=request.workflow_types,
    )
    return result


@router.delete("/delegations/{delegation_id}")
async def cancel_delegation(delegation_id: str, current_user: CurrentUser):
    """Cancel a delegation."""
    return {
        "delegation_id": delegation_id,
        "status": "cancelled",
        "cancelled_at": datetime.utcnow().isoformat(),
    }


# ============================================================================
# ROUTING ENDPOINTS
# ============================================================================


@router.get("/routing-rules/{entity_type}")
async def get_routing_rules(entity_type: str, current_user: CurrentUser):
    """Get routing rules for an entity type."""
    rules = workflow_engine.get_routing_rules(entity_type)
    return {"entity_type": entity_type, "rules": rules}


@router.post("/route")
async def route_entity(
    entity_type: str,
    entity_id: str,
    entity_data: dict,
    current_user: CurrentUser,
):
    """Route an entity based on configured rules."""
    result = workflow_engine.route_entity(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_data=entity_data,
    )
    return result


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================


@router.get("/stats")
async def get_workflow_stats(current_user: CurrentUser):
    """Get workflow statistics."""
    return workflow_engine.get_workflow_stats()
