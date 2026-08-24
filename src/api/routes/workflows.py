"""
Workflow API Routes

Features:
- Workflow template management
- Workflow instance operations

Approvals, delegation and the approvals statistics tile used to live here and are
gone; see the section comments below for what they did and what replaced them.
Approvals are now read from the domains that hold them, by
``src/api/routes/approvals.py``.
"""

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.dependencies import CurrentUser, require_permission
from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.user import User
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
        raise NotFoundError("Template not found")
    return template


# ============================================================================
# WORKFLOW INSTANCE ENDPOINTS
# ============================================================================


@router.post("/start")
async def start_workflow(
    request: WorkflowStartRequest,
    current_user: Annotated[User, Depends(require_permission("workflow:create"))],
):
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
        raise BadRequestError(result["error"])

    return result


@router.get("/instances")
async def list_workflow_instances(
    current_user: CurrentUser,
    status: Optional[str] = None,
    entity_type: Optional[str] = None,
):
    """List workflow instances."""
    return {"instances": [], "total": 0}


@router.get("/instances/{workflow_id}")
async def get_workflow_instance(workflow_id: str, current_user: CurrentUser):
    """Get workflow instance details."""
    instance = workflow_engine.get_workflow_instance(workflow_id)
    if not instance:
        raise NotFoundError("Workflow instance not found")
    return instance


@router.post("/instances/{workflow_id}/advance")
async def advance_workflow(
    workflow_id: str,
    outcome: str,
    current_user: Annotated[User, Depends(require_permission("workflow:update"))],
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
async def cancel_workflow(
    workflow_id: str,
    current_user: Annotated[User, Depends(require_permission("workflow:update"))],
    reason: Optional[str] = None,
):
    """Cancel a workflow instance."""
    return {
        "workflow_id": workflow_id,
        "status": "cancelled",
        "cancelled_by": current_user.id,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# APPROVAL ENDPOINTS — removed by FR-APPROVALS-01
# ============================================================================
#
# Four endpoints stood here: `GET /approvals/pending`, `POST
# /approvals/{id}/approve`, `POST /approvals/{id}/reject` and `POST
# /approvals/bulk-approve`. All four spoke to `WorkflowTemplateEngine`, which
# holds no state, so the queue was `[]` for every user forever and each write
# returned `{"status": "approved"}` having recorded nothing. On a quality
# management system the writes were the worse half: a permitted user could approve
# a controlled document, be told it worked, and leave no decision anywhere.
#
# The replacement is a read model, not a second engine.
# `GET /api/v1/approvals/my-decisions` reads the domains that actually hold
# pending decisions, and names any it could not read. Recording a decision stays
# with the owning domain — for controlled documents, `POST
# /api/v1/document-control/approvals/{instance_id}/action`.
#
# `tests/integration/test_approvals_my_decisions.py` fails if any of the four
# answers anything but 404 again.


# ============================================================================
# ESCALATION ENDPOINTS
# ============================================================================


@router.get("/escalations/pending")
async def get_pending_escalations(current_user: CurrentUser):
    """Get workflows pending escalation."""
    escalations = workflow_engine.check_escalations()
    return {"escalations": escalations, "total": len(escalations)}


@router.post("/instances/{workflow_id}/escalate")
async def escalate_workflow(
    workflow_id: str,
    request: EscalationRequest,
    current_user: Annotated[User, Depends(require_permission("workflow:update"))],
):
    """Escalate a workflow."""
    result = workflow_engine.escalate(
        workflow_id=workflow_id,
        escalate_to=request.escalate_to,
        reason=request.reason,
        new_priority=request.new_priority,
    )
    return result


# ============================================================================
# DELEGATION ENDPOINTS — removed by FR-APPROVALS-01
# ============================================================================
#
# `GET /delegations` returned a literal invented record — "DEL-20260115001 /
# Jane Smith / Annual leave", the same one for every caller of every tenant —
# from `WorkflowTemplateEngine.get_active_delegations`. A user could read a
# colleague's name off it and believe approval cover was arranged. `POST` and
# `DELETE` matched: both returned a success dict and stored nothing.
#
# Not reimplemented here. Delegated approval is a real requirement and needs a
# table, an audit trail and an answer for approvals already in flight; a read
# model over domain queues is not where that decision gets made. Until then the
# honest state of the product is that it has no delegation, which is what a 404
# now says.


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
    current_user: Annotated[User, Depends(require_permission("workflow:update"))],
):
    """Route an entity based on configured rules."""
    result = workflow_engine.route_entity(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_data=entity_data,
    )
    return result


# ============================================================================
# STATISTICS ENDPOINTS — removed by FR-APPROVALS-01
# ============================================================================
#
# `GET /stats` reported every figure as null except `pending_approvals`, which it
# counted from the queue removed above — so its one measured number was a
# fabricated zero, and the honest nulls beside it made that zero look measured.
# A tile reading "0 pending approvals" is the one statement this surface must
# never make without having looked.
#
# The count now comes from `GET /api/v1/approvals/my-decisions`, where it is a
# count of rows that were actually read, and any source that could not be read is
# named beside it.
