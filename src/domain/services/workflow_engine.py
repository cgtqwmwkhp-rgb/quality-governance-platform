"""
Workflow Engine - Intelligent Workflow Automation with DB Persistence

Features:
- Workflow template management (DB-backed)
- Instance creation & step advancement
- Approval chain management
- Auto-escalation
- SLA tracking
- Delegation management
- Statistics from live data
"""

import enum
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.workflow import (
    ApprovalRequest,
    EscalationLog,
    UserDelegation,
    WorkflowInstance,
    WorkflowStep,
    WorkflowTemplate,
)

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES: List[Dict[str, Any]] = [
    {
        "code": "RIDDOR",
        "name": "RIDDOR Reporting Workflow",
        "description": "Mandatory HSE notification for reportable incidents",
        "category": "regulatory",
        "trigger_entity_type": "incident",
        "trigger_conditions": {"severity": ["critical", "major"], "is_riddor": True},
        "sla_hours": 24,
        "warning_hours": 20,
        "steps": [
            {
                "name": "Initial Review",
                "type": "approval",
                "approval_type": "sequential",
                "approvers": ["safety_manager"],
                "sla_hours": 4,
            },
            {"name": "HSE Notification", "type": "task", "assignee_role": "safety_manager", "sla_hours": 8},
            {
                "name": "Management Sign-off",
                "type": "approval",
                "approval_type": "sequential",
                "approvers": ["operations_director"],
                "sla_hours": 4,
            },
            {"name": "Final Submission", "type": "task", "assignee_role": "compliance_officer", "sla_hours": 4},
        ],
        "escalation_rules": [{"trigger": "sla_breach", "escalate_to": "operations_director", "priority": "critical"}],
    },
    {
        "code": "CAPA",
        "name": "Corrective/Preventive Action Workflow",
        "description": "Track and verify corrective and preventive actions",
        "category": "quality",
        "trigger_entity_type": "action",
        "trigger_conditions": {"type": ["corrective", "preventive"]},
        "sla_hours": 168,
        "warning_hours": 120,
        "steps": [
            {"name": "Root Cause Analysis", "type": "task", "assignee": "action_owner", "sla_hours": 48},
            {
                "name": "Action Plan Review",
                "type": "approval",
                "approval_type": "sequential",
                "approvers": ["quality_manager"],
                "sla_hours": 24,
            },
            {"name": "Implementation", "type": "task", "assignee": "action_owner", "sla_hours": 72},
            {
                "name": "Effectiveness Verification",
                "type": "approval",
                "approval_type": "sequential",
                "approvers": ["quality_manager"],
                "sla_hours": 24,
            },
        ],
    },
    {
        "code": "NCR",
        "name": "Non-Conformance Report Workflow",
        "description": "Handle non-conformances through to resolution",
        "category": "quality",
        "trigger_entity_type": "audit_finding",
        "trigger_conditions": {"type": "non_conformance"},
        "sla_hours": 72,
        "warning_hours": 48,
        "steps": [
            {"name": "NCR Registration", "type": "task", "assignee_role": "quality_team", "sla_hours": 8},
            {"name": "Root Cause Investigation", "type": "task", "assignee": "finding_owner", "sla_hours": 24},
            {
                "name": "Corrective Action Plan",
                "type": "approval",
                "approval_type": "parallel",
                "approvers": ["quality_manager", "department_head"],
                "sla_hours": 16,
            },
            {"name": "Implementation & Closure", "type": "task", "assignee": "finding_owner", "sla_hours": 24},
        ],
    },
    {
        "code": "INCIDENT_INVESTIGATION",
        "name": "Incident Investigation Workflow",
        "description": "Structured incident investigation process",
        "category": "safety",
        "trigger_entity_type": "incident",
        "trigger_conditions": {"requires_investigation": True},
        "sla_hours": 120,
        "warning_hours": 96,
        "steps": [
            {"name": "Initial Assessment", "type": "task", "assignee_role": "safety_manager", "sla_hours": 4},
            {"name": "Evidence Collection", "type": "task", "assignee_role": "investigator", "sla_hours": 24},
            {"name": "Root Cause Analysis", "type": "task", "assignee_role": "investigator", "sla_hours": 48},
            {
                "name": "Findings Review",
                "type": "approval",
                "approval_type": "sequential",
                "approvers": ["safety_manager", "operations_manager"],
                "sla_hours": 24,
            },
            {"name": "Action Assignment", "type": "task", "assignee_role": "safety_manager", "sla_hours": 8},
            {
                "name": "Management Sign-off",
                "type": "approval",
                "approval_type": "sequential",
                "approvers": ["operations_director"],
                "sla_hours": 16,
            },
        ],
    },
    {
        "code": "DOCUMENT_APPROVAL",
        "name": "Document Approval Workflow",
        "description": "Review and approve new/updated documents",
        "category": "documents",
        "trigger_entity_type": "document",
        "trigger_conditions": {"status": "pending_approval"},
        "sla_hours": 48,
        "warning_hours": 36,
        "steps": [
            {
                "name": "Technical Review",
                "type": "approval",
                "approval_type": "sequential",
                "approvers": ["document_owner"],
                "sla_hours": 24,
            },
            {
                "name": "Quality Review",
                "type": "approval",
                "approval_type": "sequential",
                "approvers": ["quality_manager"],
                "sla_hours": 16,
            },
            {
                "name": "Final Approval",
                "type": "approval",
                "approval_type": "sequential",
                "approvers": ["document_controller"],
                "sla_hours": 8,
            },
        ],
    },
]


async def seed_default_templates(db: AsyncSession) -> int:
    """Insert default templates if they don't already exist. Returns count of newly created."""
    created = 0
    for tpl in DEFAULT_TEMPLATES:
        result = await db.execute(select(WorkflowTemplate).where(WorkflowTemplate.code == tpl["code"]))
        if result.scalar_one_or_none() is None:
            db.add(
                WorkflowTemplate(
                    name=tpl["name"],
                    code=tpl["code"],
                    description=tpl["description"],
                    category=tpl["category"],
                    trigger_entity_type=tpl["trigger_entity_type"],
                    trigger_conditions=tpl.get("trigger_conditions"),
                    sla_hours=tpl.get("sla_hours"),
                    warning_hours=tpl.get("warning_hours"),
                    steps=tpl["steps"],
                    escalation_rules=tpl.get("escalation_rules"),
                )
            )
            created += 1
    if created:
        await db.flush()
    return created


async def list_templates(db: AsyncSession, category: Optional[str] = None) -> List[WorkflowTemplate]:
    query = select(WorkflowTemplate).where(WorkflowTemplate.is_active == True)  # noqa: E712
    if category:
        query = query.where(WorkflowTemplate.category == category)
    query = query.order_by(WorkflowTemplate.name)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_template(db: AsyncSession, template_code: str) -> Optional[WorkflowTemplate]:
    result = await db.execute(select(WorkflowTemplate).where(WorkflowTemplate.code == template_code))
    return result.scalar_one_or_none()


async def start_workflow(
    db: AsyncSession,
    template_code: str,
    entity_type: str,
    entity_id: str,
    initiated_by: int,
    context: Optional[Dict[str, Any]] = None,
    priority: str = "normal",
) -> WorkflowInstance:
    """Start a new workflow instance from a template, persisting to DB."""
    template = await get_template(db, template_code)
    if template is None:
        raise ValueError(f"Template not found: {template_code}")

    now = datetime.utcnow()
    sla_due = now + timedelta(hours=template.sla_hours or 72)
    warning_at = now + timedelta(hours=template.warning_hours or 48)

    step_defs: list = template.steps  # type: ignore[assignment]

    instance = WorkflowInstance(
        template_id=template.id,
        entity_type=entity_type,
        entity_id=entity_id,
        status="in_progress",
        priority=priority,
        current_step=0,
        current_step_name=step_defs[0]["name"] if step_defs else None,
        initiated_by=initiated_by,
        sla_due_at=sla_due,
        sla_warning_at=warning_at,
        sla_breached=False,
        context=context or {},
        started_at=now,
    )
    db.add(instance)
    await db.flush()

    cumulative_hours = 0
    for i, step_def in enumerate(step_defs):
        step_sla = step_def.get("sla_hours", 24)
        cumulative_hours += step_sla
        due_at = now + timedelta(hours=cumulative_hours)

        step = WorkflowStep(
            instance_id=instance.id,
            step_number=i,
            step_name=step_def["name"],
            step_type=step_def["type"],
            approval_type=step_def.get("approval_type"),
            required_approvers=step_def.get("approvers", []),
            status="in_progress" if i == 0 else "pending",
            due_at=due_at,
            started_at=now if i == 0 else None,
        )
        db.add(step)

    await db.flush()
    logger.info("Started workflow instance %s from template %s", instance.id, template_code)
    return instance


async def get_instance(db: AsyncSession, instance_id: int) -> Optional[WorkflowInstance]:
    result = await db.execute(select(WorkflowInstance).where(WorkflowInstance.id == instance_id))
    return result.scalar_one_or_none()


async def get_instance_steps(db: AsyncSession, instance_id: int) -> List[WorkflowStep]:
    result = await db.execute(
        select(WorkflowStep).where(WorkflowStep.instance_id == instance_id).order_by(WorkflowStep.step_number)
    )
    return list(result.scalars().all())


async def list_instances(
    db: AsyncSession,
    status: Optional[str] = None,
    entity_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[List[WorkflowInstance], int]:
    """Return (instances, total_count)."""
    query = select(WorkflowInstance)
    count_q = select(func.count(WorkflowInstance.id))

    filters = []
    if status:
        filters.append(WorkflowInstance.status == status)
    if entity_type:
        filters.append(WorkflowInstance.entity_type == entity_type)

    if filters:
        query = query.where(and_(*filters))
        count_q = count_q.where(and_(*filters))

    total_res = await db.execute(count_q)
    total = total_res.scalar() or 0

    query = query.order_by(WorkflowInstance.started_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    return list(result.scalars().all()), total


async def advance_workflow(
    db: AsyncSession,
    instance_id: int,
    outcome: str,
    outcome_by: int,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Complete the current step and advance to the next one."""
    instance = await get_instance(db, instance_id)
    if instance is None:
        raise ValueError(f"Workflow instance {instance_id} not found")

    now = datetime.utcnow()

    # Find current step
    steps = await get_instance_steps(db, instance_id)
    current_idx = instance.current_step
    if current_idx >= len(steps):
        raise ValueError("Workflow already completed")

    current_step = steps[current_idx]
    current_step.status = "completed"
    current_step.outcome = outcome
    current_step.outcome_by = outcome_by
    current_step.outcome_reason = notes
    current_step.outcome_at = now
    current_step.completed_at = now

    next_idx = current_idx + 1
    if next_idx < len(steps):
        next_step = steps[next_idx]
        next_step.status = "in_progress"
        next_step.started_at = now

        instance.current_step = next_idx
        instance.current_step_name = next_step.step_name
        instance.status = "in_progress"
    else:
        instance.status = "completed"
        instance.completed_at = now
        instance.current_step_name = None

    instance.updated_at = now
    await db.flush()

    logger.info("Advanced workflow %s — step %s → %s", instance_id, current_step.step_name, outcome)

    return {
        "workflow_id": instance_id,
        "action": "advanced",
        "outcome": outcome,
        "outcome_by": outcome_by,
        "notes": notes,
        "next_step": instance.current_step_name,
        "status": instance.status,
        "timestamp": now.isoformat(),
    }


async def cancel_workflow(
    db: AsyncSession,
    instance_id: int,
    cancelled_by: int,
    reason: Optional[str] = None,
) -> WorkflowInstance:
    instance = await get_instance(db, instance_id)
    if instance is None:
        raise ValueError(f"Workflow instance {instance_id} not found")

    now = datetime.utcnow()
    instance.status = "cancelled"
    instance.completed_at = now
    instance.updated_at = now

    # Cancel any in-progress steps
    await db.execute(
        update(WorkflowStep)
        .where(
            and_(
                WorkflowStep.instance_id == instance_id,
                WorkflowStep.status.in_(["pending", "in_progress"]),
            )
        )
        .values(status="cancelled", completed_at=now)
    )
    await db.flush()
    return instance


# ==================== Approval Management ====================


async def get_pending_approvals(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """Get all pending approval steps for workflows. Returns enriched dicts."""
    result = await db.execute(
        select(WorkflowStep, WorkflowInstance, WorkflowTemplate)
        .join(WorkflowInstance, WorkflowStep.instance_id == WorkflowInstance.id)
        .join(WorkflowTemplate, WorkflowInstance.template_id == WorkflowTemplate.id)
        .where(
            and_(
                WorkflowStep.status == "in_progress",
                WorkflowStep.step_type == "approval",
            )
        )
        .order_by(WorkflowStep.due_at.asc())
    )

    approvals = []
    for step, inst, tpl in result.all():
        now = datetime.utcnow()
        sla_status = "ok"
        if step.due_at:
            if now > step.due_at:
                sla_status = "breached"
            elif step.due_at - now < timedelta(hours=4):
                sla_status = "warning"

        approvals.append(
            {
                "id": step.id,
                "workflow_id": inst.id,
                "workflow_name": tpl.name,
                "step_name": step.step_name,
                "entity_type": inst.entity_type,
                "entity_id": inst.entity_id,
                "entity_title": f"{inst.entity_type.title()} {inst.entity_id}",
                "requested_at": (step.started_at or inst.started_at).isoformat(),
                "due_at": step.due_at.isoformat() if step.due_at else None,
                "priority": inst.priority,
                "sla_status": sla_status,
            }
        )

    return approvals


async def approve_step(
    db: AsyncSession,
    step_id: int,
    user_id: int,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Approve the given step and advance the workflow."""
    result = await db.execute(select(WorkflowStep).where(WorkflowStep.id == step_id))
    step = result.scalar_one_or_none()
    if step is None:
        raise ValueError(f"Step {step_id} not found")
    if step.status != "in_progress":
        raise ValueError(f"Step is not awaiting action (status={step.status})")

    return await advance_workflow(
        db,
        instance_id=step.instance_id,
        outcome="approved",
        outcome_by=user_id,
        notes=notes,
    )


async def reject_step(
    db: AsyncSession,
    step_id: int,
    user_id: int,
    reason: str,
) -> Dict[str, Any]:
    """Reject the given step, marking the workflow as rejected."""
    result = await db.execute(select(WorkflowStep).where(WorkflowStep.id == step_id))
    step = result.scalar_one_or_none()
    if step is None:
        raise ValueError(f"Step {step_id} not found")

    now = datetime.utcnow()
    step.status = "completed"
    step.outcome = "rejected"
    step.outcome_by = user_id
    step.outcome_reason = reason
    step.outcome_at = now
    step.completed_at = now

    instance = await get_instance(db, step.instance_id)
    if instance:
        instance.status = "rejected"
        instance.updated_at = now

    await db.flush()
    return {
        "workflow_id": step.instance_id,
        "step_id": step_id,
        "action": "rejected",
        "rejected_by": user_id,
        "reason": reason,
        "timestamp": now.isoformat(),
    }


async def bulk_approve(
    db: AsyncSession,
    step_ids: List[int],
    user_id: int,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    results = []
    errors = []
    for sid in step_ids:
        try:
            r = await approve_step(db, sid, user_id, notes)
            results.append(r)
        except Exception as exc:
            errors.append({"step_id": sid, "error": str(exc)})

    return {
        "processed": len(step_ids),
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }


# ==================== Escalation ====================


async def check_escalations(db: AsyncSession) -> List[Dict[str, Any]]:
    """Find workflows with breached SLAs."""
    now = datetime.utcnow()
    result = await db.execute(
        select(WorkflowInstance, WorkflowTemplate)
        .join(WorkflowTemplate, WorkflowInstance.template_id == WorkflowTemplate.id)
        .where(
            and_(
                WorkflowInstance.status.in_(["in_progress", "awaiting_approval"]),
                WorkflowInstance.sla_due_at < now,
                WorkflowInstance.sla_breached == False,  # noqa: E712
            )
        )
    )

    escalations = []
    for inst, tpl in result.all():
        hours_overdue = int((now - inst.sla_due_at).total_seconds() / 3600)
        inst.sla_breached = True
        inst.updated_at = now

        escalations.append(
            {
                "workflow_id": inst.id,
                "template": tpl.code,
                "reason": "SLA breach",
                "hours_overdue": hours_overdue,
                "current_step": inst.current_step_name,
                "recommended_action": "Escalate to management",
            }
        )

    if escalations:
        await db.flush()

    return escalations


async def escalate_workflow(
    db: AsyncSession,
    instance_id: int,
    escalated_by: int,
    reason: str,
    new_priority: Optional[str] = None,
) -> Dict[str, Any]:
    instance = await get_instance(db, instance_id)
    if instance is None:
        raise ValueError(f"Workflow instance {instance_id} not found")

    now = datetime.utcnow()
    old_priority = instance.priority
    instance.status = "escalated"
    if new_priority:
        instance.priority = new_priority
    instance.updated_at = now

    log = EscalationLog(
        instance_id=instance_id,
        trigger="manual",
        from_user_id=escalated_by,
        previous_priority=old_priority,
        new_priority=new_priority or old_priority,
        reason=reason,
        escalated_at=now,
    )
    db.add(log)
    await db.flush()

    return {
        "workflow_id": instance_id,
        "escalated_by": escalated_by,
        "reason": reason,
        "new_priority": new_priority or old_priority,
        "escalated_at": now.isoformat(),
    }


# ==================== Delegation ====================


async def get_active_delegations(db: AsyncSession, user_id: int) -> List[UserDelegation]:
    now = datetime.utcnow()
    result = await db.execute(
        select(UserDelegation).where(
            and_(
                UserDelegation.user_id == user_id,
                UserDelegation.is_active == True,  # noqa: E712
                UserDelegation.end_date > now,
            )
        )
    )
    return list(result.scalars().all())


async def set_delegation(
    db: AsyncSession,
    user_id: int,
    delegate_id: int,
    start_date: datetime,
    end_date: datetime,
    reason: Optional[str] = None,
    workflow_types: Optional[List[str]] = None,
) -> UserDelegation:
    delegation = UserDelegation(
        user_id=user_id,
        delegate_id=delegate_id,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        delegate_all=workflow_types is None,
        workflow_types=workflow_types,
        is_active=True,
    )
    db.add(delegation)
    await db.flush()
    return delegation


async def cancel_delegation(db: AsyncSession, delegation_id: int) -> bool:
    result = await db.execute(select(UserDelegation).where(UserDelegation.id == delegation_id))
    delegation = result.scalar_one_or_none()
    if delegation is None:
        return False
    delegation.is_active = False
    await db.flush()
    return True


# ==================== Statistics ====================


async def get_workflow_stats(db: AsyncSession) -> Dict[str, Any]:
    """Compute live statistics from the database."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    # Total counts by status
    status_counts = {}
    result = await db.execute(
        select(WorkflowInstance.status, func.count(WorkflowInstance.id)).group_by(WorkflowInstance.status)
    )
    for row_status, cnt in result.all():
        status_counts[row_status] = cnt

    active = sum(status_counts.get(s, 0) for s in ["in_progress", "awaiting_approval", "escalated", "pending"])

    # Overdue
    overdue_res = await db.execute(
        select(func.count(WorkflowInstance.id)).where(
            and_(
                WorkflowInstance.status.in_(["in_progress", "awaiting_approval"]),
                WorkflowInstance.sla_due_at < now,
            )
        )
    )
    overdue = overdue_res.scalar() or 0

    # Completed today
    completed_today_res = await db.execute(
        select(func.count(WorkflowInstance.id)).where(
            and_(
                WorkflowInstance.status == "completed",
                WorkflowInstance.completed_at >= today_start,
            )
        )
    )
    completed_today = completed_today_res.scalar() or 0

    # Completed this week
    completed_week_res = await db.execute(
        select(func.count(WorkflowInstance.id)).where(
            and_(
                WorkflowInstance.status == "completed",
                WorkflowInstance.completed_at >= week_start,
            )
        )
    )
    completed_week = completed_week_res.scalar() or 0

    # Pending approval steps
    pending_approvals_res = await db.execute(
        select(func.count(WorkflowStep.id)).where(
            and_(
                WorkflowStep.status == "in_progress",
                WorkflowStep.step_type == "approval",
            )
        )
    )
    pending_approvals = pending_approvals_res.scalar() or 0

    # By priority
    priority_res = await db.execute(
        select(WorkflowInstance.priority, func.count(WorkflowInstance.id))
        .where(WorkflowInstance.status.in_(["in_progress", "awaiting_approval", "escalated", "pending"]))
        .group_by(WorkflowInstance.priority)
    )
    by_priority = {p: c for p, c in priority_res.all()}

    return {
        "active_workflows": active,
        "pending_approvals": pending_approvals,
        "overdue": overdue,
        "completed_today": completed_today,
        "completed_this_week": completed_week,
        "by_status": status_counts,
        "by_priority": by_priority,
    }


# ---------------------------------------------------------------------------
# Backward-compatible exports expected by existing tests and callers
# ---------------------------------------------------------------------------


class WorkflowStepType(str, enum.Enum):
    APPROVAL = "approval"
    TASK = "task"
    NOTIFICATION = "notification"
    CONDITIONAL = "conditional"


class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"
    FAILED = "failed"


class WorkflowEngine:
    """Backward-compatible wrapper around module-level functions."""

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self.templates = DEFAULT_TEMPLATES

    async def seed_defaults(self) -> int:
        if self.db is None:
            return 0
        return await seed_default_templates(self.db)

    async def start(self, template_code: str, entity_type: str, entity_id: str, **kwargs):
        if self.db is None:
            raise RuntimeError("No DB session provided")
        return await start_workflow(self.db, template_code, entity_type, entity_id, **kwargs)

    async def list_instances_compat(self, **kwargs):
        if self.db is None:
            return []
        return await list_instances(self.db, **kwargs)

    async def get_stats(self):
        if self.db is None:
            return {}
        return await get_workflow_stats(self.db)
