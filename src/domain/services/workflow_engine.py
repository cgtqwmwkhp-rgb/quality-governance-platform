"""
Workflow Engine - Consolidated Workflow Automation

Features:
- Workflow template management (DB-backed)
- Instance creation & step advancement
- Approval chain management
- Auto-escalation
- SLA tracking
- Delegation management
- Statistics from live data
- Rule-based condition evaluation (ConditionEvaluator / RuleEvaluator)
- Action execution (email, SMS, assign, status change, escalation, webhooks)
- SLA service with business hours calculation
- In-memory workflow service (WorkflowService)
"""

import enum
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

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
from src.domain.models.workflow_rules import (
    ActionType,
    EntityType,
    EscalationLevel,
    RuleExecution,
    SLAConfiguration,
    SLATracking,
    TriggerEvent,
    WorkflowRule,
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
            {
                "name": "HSE Notification",
                "type": "task",
                "assignee_role": "safety_manager",
                "sla_hours": 8,
            },
            {
                "name": "Management Sign-off",
                "type": "approval",
                "approval_type": "sequential",
                "approvers": ["operations_director"],
                "sla_hours": 4,
            },
            {
                "name": "Final Submission",
                "type": "task",
                "assignee_role": "compliance_officer",
                "sla_hours": 4,
            },
        ],
        "escalation_rules": [
            {
                "trigger": "sla_breach",
                "escalate_to": "operations_director",
                "priority": "critical",
            }
        ],
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
            {
                "name": "Root Cause Analysis",
                "type": "task",
                "assignee": "action_owner",
                "sla_hours": 48,
            },
            {
                "name": "Action Plan Review",
                "type": "approval",
                "approval_type": "sequential",
                "approvers": ["quality_manager"],
                "sla_hours": 24,
            },
            {
                "name": "Implementation",
                "type": "task",
                "assignee": "action_owner",
                "sla_hours": 72,
            },
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
            {
                "name": "NCR Registration",
                "type": "task",
                "assignee_role": "quality_team",
                "sla_hours": 8,
            },
            {
                "name": "Root Cause Investigation",
                "type": "task",
                "assignee": "finding_owner",
                "sla_hours": 24,
            },
            {
                "name": "Corrective Action Plan",
                "type": "approval",
                "approval_type": "parallel",
                "approvers": ["quality_manager", "department_head"],
                "sla_hours": 16,
            },
            {
                "name": "Implementation & Closure",
                "type": "task",
                "assignee": "finding_owner",
                "sla_hours": 24,
            },
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
            {
                "name": "Initial Assessment",
                "type": "task",
                "assignee_role": "safety_manager",
                "sla_hours": 4,
            },
            {
                "name": "Evidence Collection",
                "type": "task",
                "assignee_role": "investigator",
                "sla_hours": 24,
            },
            {
                "name": "Root Cause Analysis",
                "type": "task",
                "assignee_role": "investigator",
                "sla_hours": 48,
            },
            {
                "name": "Findings Review",
                "type": "approval",
                "approval_type": "sequential",
                "approvers": ["safety_manager", "operations_manager"],
                "sla_hours": 24,
            },
            {
                "name": "Action Assignment",
                "type": "task",
                "assignee_role": "safety_manager",
                "sla_hours": 8,
            },
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

    now = datetime.now(timezone.utc)
    sla_due = now + timedelta(hours=template.sla_hours or 72)
    warning_at = now + timedelta(hours=template.warning_hours or 48)

    step_defs = list(template.steps) if template.steps else []

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
    total: int = total_res.scalar() or 0  # type: ignore[assignment]  # scalar returns Row|None, coerced to int  # TYPE-IGNORE: MYPY-OVERRIDE

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

    now = datetime.now(timezone.utc)

    # Find current step
    steps = await get_instance_steps(db, instance_id)
    current_idx: int = instance.current_step  # type: ignore[assignment]  # SA column value  # TYPE-IGNORE: MYPY-OVERRIDE
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

    logger.info(
        "Advanced workflow %s — step %s → %s",
        instance_id,
        current_step.step_name,
        outcome,
    )

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

    now = datetime.now(timezone.utc)
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
        now = datetime.now(timezone.utc)
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

    now = datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
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

    now = datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
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
    PARALLEL = "parallel"
    AUTOMATIC = "automatic"


class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
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


# ==================== Rule Evaluation (from services.workflow_engine) ====================


class ConditionEvaluator:
    """Evaluates rule conditions against entity data."""

    OPERATORS = {
        "equals": lambda a, b: a == b,
        "not_equals": lambda a, b: a != b,
        "contains": lambda a, b: b in a if a else False,
        "not_contains": lambda a, b: b not in a if a else True,
        "starts_with": lambda a, b: a.startswith(b) if a else False,
        "ends_with": lambda a, b: a.endswith(b) if a else False,
        "greater_than": lambda a, b: a > b if a is not None else False,
        "less_than": lambda a, b: a < b if a is not None else False,
        "greater_or_equal": lambda a, b: a >= b if a is not None else False,
        "less_or_equal": lambda a, b: a <= b if a is not None else False,
        "in": lambda a, b: a in b if isinstance(b, list) else a == b,
        "not_in": lambda a, b: a not in b if isinstance(b, list) else a != b,
        "is_empty": lambda a, b: not a,
        "is_not_empty": lambda a, b: bool(a),
        "is_null": lambda a, b: a is None,
        "is_not_null": lambda a, b: a is not None,
    }

    @classmethod
    def evaluate(cls, conditions: Optional[Dict], entity_data: Dict[str, Any]) -> bool:
        """Evaluate conditions against entity data.

        Args:
            conditions: Condition definition (JSON structure)
            entity_data: Entity fields as dictionary

        Returns:
            True if conditions are met, False otherwise
        """
        if not conditions:
            return True

        if "and" in conditions:
            return all(cls.evaluate(c, entity_data) for c in conditions["and"])

        if "or" in conditions:
            return any(cls.evaluate(c, entity_data) for c in conditions["or"])

        if "not" in conditions:
            return not cls.evaluate(conditions["not"], entity_data)

        field_name = conditions.get("field")
        operator = conditions.get("operator")
        value = conditions.get("value")

        if not field_name or not operator:
            logger.warning(f"Invalid condition structure: {conditions}")
            return False

        entity_value = cls._get_nested_value(entity_data, field_name)

        op_func = cls.OPERATORS.get(operator)
        if not op_func:
            logger.warning(f"Unknown operator: {operator}")
            return False

        try:
            return op_func(entity_value, value)
        except Exception as e:
            logger.warning(f"Error evaluating condition: {e}")
            return False

    @staticmethod
    def _get_nested_value(data: Dict, field_name: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = field_name.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE
            else:
                return None
        return value


class ActionExecutor:
    """Executes workflow actions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(
        self,
        action_type: ActionType,
        action_config: Dict,
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute an action based on type and config."""
        executor_method = getattr(self, f"_execute_{action_type.value}", None)
        if not executor_method:
            logger.warning(f"No executor for action type: {action_type}")
            return {"success": False, "error": f"Unknown action type: {action_type}"}

        try:
            result = await executor_method(action_config, entity_type, entity_id, entity_data)
            return {"success": True, **result}
        except Exception as e:
            logger.error(f"Error executing action {action_type}: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_send_email(
        self, config: Dict, entity_type: EntityType, entity_id: int, entity_data: Dict
    ) -> Dict:
        template = config.get("template", "default")
        recipients = config.get("recipients", [])
        subject = config.get("subject", f"Notification for {entity_type.value} #{entity_id}")
        logger.info(f"Would send email: template={template}, recipients={recipients}, subject={subject}")
        return {
            "action": "send_email",
            "template": template,
            "recipients": recipients,
            "subject": subject,
            "queued": True,
        }

    async def _execute_send_sms(self, config: Dict, entity_type: EntityType, entity_id: int, entity_data: Dict) -> Dict:
        phone = config.get("phone")
        message = config.get("message", f"Alert for {entity_type.value} #{entity_id}")
        logger.info(f"Would send SMS: phone={phone}, message={message}")
        return {"action": "send_sms", "phone": phone, "queued": True}

    async def _execute_assign_to_user(
        self, config: Dict, entity_type: EntityType, entity_id: int, entity_data: Dict
    ) -> Dict:
        user_id = config.get("user_id")
        model = self._get_model_for_entity(entity_type)
        if model:
            from sqlalchemy import update as sa_update

            await self.db.execute(sa_update(model).where(model.id == entity_id).values(assigned_to_id=user_id))
            await self.db.commit()
        return {"action": "assign_to_user", "user_id": user_id, "completed": True}

    async def _execute_assign_to_role(
        self, config: Dict, entity_type: EntityType, entity_id: int, entity_data: Dict
    ) -> Dict:
        role = config.get("role")
        department = config.get("department", entity_data.get("department"))
        logger.info(f"Would assign to role: {role} in department: {department}")
        return {
            "action": "assign_to_role",
            "role": role,
            "department": department,
            "pending_user_lookup": True,
        }

    async def _execute_change_status(
        self, config: Dict, entity_type: EntityType, entity_id: int, entity_data: Dict
    ) -> Dict:
        new_status = config.get("new_status")
        model = self._get_model_for_entity(entity_type)
        if model:
            from sqlalchemy import update as sa_update

            await self.db.execute(sa_update(model).where(model.id == entity_id).values(status=new_status))
            await self.db.commit()
        return {"action": "change_status", "new_status": new_status, "completed": True}

    async def _execute_change_priority(
        self, config: Dict, entity_type: EntityType, entity_id: int, entity_data: Dict
    ) -> Dict:
        new_priority = config.get("new_priority")
        model = self._get_model_for_entity(entity_type)
        if model:
            from sqlalchemy import update as sa_update

            await self.db.execute(sa_update(model).where(model.id == entity_id).values(priority=new_priority))
            await self.db.commit()
        return {
            "action": "change_priority",
            "new_priority": new_priority,
            "completed": True,
        }

    async def _execute_escalate(self, config: Dict, entity_type: EntityType, entity_id: int, entity_data: Dict) -> Dict:
        current_level = entity_data.get("escalation_level", 0)
        new_level = current_level + 1

        result = await self.db.execute(
            select(EscalationLevel).where(
                and_(
                    EscalationLevel.entity_type == entity_type,  # type: ignore[arg-type]  # SA column comparison  # TYPE-IGNORE: MYPY-OVERRIDE
                    EscalationLevel.level == new_level,  # type: ignore[attr-defined]  # SA column  # TYPE-IGNORE: MYPY-OVERRIDE
                    EscalationLevel.is_active == True,  # type: ignore[attr-defined]  # SA column  # noqa: E712  # TYPE-IGNORE: MYPY-OVERRIDE
                )
            )
        )
        escalation = result.scalar_one_or_none()

        if escalation:
            model = self._get_model_for_entity(entity_type)
            if model:
                from sqlalchemy import update as sa_update

                await self.db.execute(
                    sa_update(model).where(model.id == entity_id).values(escalation_level=new_level, status="escalated")
                )
                await self.db.commit()

            if escalation.escalate_to_user_id:
                await self._execute_assign_to_user(
                    {"user_id": escalation.escalate_to_user_id},
                    entity_type,
                    entity_id,
                    entity_data,
                )

            return {
                "action": "escalate",
                "new_level": new_level,
                "escalate_to_role": escalation.escalate_to_role,
                "completed": True,
            }

        return {
            "action": "escalate",
            "new_level": new_level,
            "completed": False,
            "reason": "No escalation level configured",
        }

    async def _execute_update_risk_score(
        self, config: Dict, entity_type: EntityType, entity_id: int, entity_data: Dict
    ) -> Dict:
        risk_id = config.get("risk_id") or entity_data.get("risk_id")
        score_adjustment = config.get("score_adjustment", 0)
        logger.info(f"Would update risk score: risk_id={risk_id}, adjustment={score_adjustment}")
        return {
            "action": "update_risk_score",
            "risk_id": risk_id,
            "adjustment": score_adjustment,
        }

    async def _execute_log_audit_event(
        self, config: Dict, entity_type: EntityType, entity_id: int, entity_data: Dict
    ) -> Dict:
        event_type = config.get("event_type", "workflow_action")
        logger.info(f"Audit event: {event_type} for {entity_type.value} #{entity_id}")
        return {"action": "log_audit_event", "event_type": event_type, "logged": True}

    async def _execute_create_task(
        self, config: Dict, entity_type: EntityType, entity_id: int, entity_data: Dict
    ) -> Dict:
        title = config.get("title", f"Follow-up for {entity_type.value} #{entity_id}")
        due_days = config.get("due_days", 7)
        logger.info(f"Would create task: {title}, due in {due_days} days")
        return {
            "action": "create_task",
            "title": title,
            "due_days": due_days,
            "created": True,
        }

    async def _execute_webhook(self, config: Dict, entity_type: EntityType, entity_id: int, entity_data: Dict) -> Dict:
        url = config.get("url")
        method = config.get("method", "POST")
        logger.info(f"Would call webhook: {method} {url}")
        return {"action": "webhook", "url": url, "method": method, "queued": True}

    def _get_model_for_entity(self, entity_type: EntityType):
        """Get SQLAlchemy model for entity type."""
        from src.domain.models.complaint import Complaint
        from src.domain.models.incident import Incident
        from src.domain.models.near_miss import NearMiss
        from src.domain.models.rta import RTA

        models = {
            EntityType.INCIDENT: Incident,
            EntityType.NEAR_MISS: NearMiss,
            EntityType.COMPLAINT: Complaint,
            EntityType.RTA: RTA,
        }
        return models.get(entity_type)


class RuleEvaluator:
    """Rule-based workflow engine that evaluates conditions and executes actions.

    Processes trigger events, matches them against configured rules,
    evaluates conditions, and executes corresponding actions.
    Also handles escalation and SLA breach checking.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.condition_evaluator = ConditionEvaluator()
        self.action_executor = ActionExecutor(db)

    async def process_event(
        self,
        entity_type: EntityType,
        entity_id: int,
        trigger_event: TriggerEvent,
        entity_data: Dict[str, Any],
        old_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Process a trigger event and execute matching rules."""
        rules = await self._get_matching_rules(entity_type, trigger_event, entity_data)

        results = []
        for rule in rules:
            if not self.condition_evaluator.evaluate(rule.conditions, entity_data):
                continue

            action_result = await self.action_executor.execute(
                rule.action_type,
                rule.action_config,
                entity_type,
                entity_id,
                entity_data,
            )

            execution = RuleExecution(
                rule_id=rule.id,
                entity_type=entity_type,
                entity_id=entity_id,
                trigger_event=trigger_event,
                executed_at=datetime.now(timezone.utc),
                success=action_result.get("success", False),
                error_message=action_result.get("error"),
                action_taken=f"{rule.action_type.value}: {rule.name}",
                action_result=action_result,
            )
            self.db.add(execution)

            results.append(
                {
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "action_type": rule.action_type.value,
                    **action_result,
                }
            )

            if rule.stop_processing:
                break

        await self.db.commit()
        return results

    async def _get_matching_rules(
        self,
        entity_type: EntityType,
        trigger_event: TriggerEvent,
        entity_data: Dict[str, Any],
    ) -> List[WorkflowRule]:
        """Get rules that match the entity type and trigger event."""
        query = (
            select(WorkflowRule)
            .where(
                and_(
                    WorkflowRule.entity_type == entity_type,
                    WorkflowRule.trigger_event == trigger_event,
                    WorkflowRule.is_active == True,
                )
            )
            .order_by(WorkflowRule.priority)
        )

        department = entity_data.get("department")
        contract = entity_data.get("contract")

        result = await self.db.execute(query)
        rules = result.scalars().all()

        matching_rules = []
        for rule in rules:
            if rule.department and rule.department != department:
                continue
            if rule.contract and rule.contract != contract:
                continue
            matching_rules.append(rule)

        return matching_rules

    async def check_escalations(self) -> List[Dict[str, Any]]:
        """Check and process pending escalations (called periodically by scheduler)."""
        results = []  # type: ignore[var-annotated]  # TYPE-IGNORE: MYPY-OVERRIDE

        query = select(WorkflowRule).where(
            and_(
                WorkflowRule.rule_type == "escalation",
                WorkflowRule.is_active == True,
                WorkflowRule.delay_hours.isnot(None),
            )
        )

        result = await self.db.execute(query)
        rules = result.scalars().all()

        for rule in rules:
            model = self.action_executor._get_model_for_entity(rule.entity_type)
            if not model:
                continue

            threshold = datetime.now(timezone.utc) - timedelta(hours=rule.delay_hours)  # type: ignore[arg-type]  # TYPE-IGNORE: MYPY-OVERRIDE
            delay_field = rule.delay_from_field or "created_at"

            logger.info(f"Checking escalation rule: {rule.name}")

        return results

    async def check_sla_breaches(self) -> List[Dict[str, Any]]:
        """Check for SLA warnings and breaches (called periodically by scheduler)."""
        now = datetime.now(timezone.utc)
        results = []

        warning_query = select(SLATracking).where(
            and_(
                SLATracking.warning_sent == False,
                SLATracking.is_breached == False,
                SLATracking.resolved_at.is_(None),
                SLATracking.is_paused == False,
            )
        )

        result = await self.db.execute(warning_query)
        trackings = result.scalars().all()

        for tracking in trackings:
            config_result = await self.db.execute(
                select(SLAConfiguration).where(SLAConfiguration.id == tracking.sla_config_id)
            )
            config = config_result.scalar_one_or_none()

            if not config:
                continue

            resolution_due = tracking.resolution_due
            started_at = tracking.started_at
            if not resolution_due or not started_at:
                continue
            total_duration = (resolution_due - started_at).total_seconds() / 3600
            elapsed = (now - started_at).total_seconds() / 3600
            percent_elapsed = (elapsed / total_duration) * 100 if total_duration > 0 else 100

            if percent_elapsed >= config.warning_threshold_percent and not tracking.warning_sent:
                await self.process_event(
                    tracking.entity_type,
                    tracking.entity_id,
                    TriggerEvent.SLA_WARNING,
                    {
                        "sla_tracking_id": tracking.id,
                        "percent_elapsed": percent_elapsed,
                    },
                )
                tracking.warning_sent = True
                results.append(
                    {
                        "entity_type": tracking.entity_type.value,
                        "entity_id": tracking.entity_id,
                        "event": "sla_warning",
                        "percent_elapsed": percent_elapsed,
                    }
                )

            if now > tracking.resolution_due and not tracking.is_breached:
                await self.process_event(
                    tracking.entity_type,
                    tracking.entity_id,
                    TriggerEvent.SLA_BREACH,
                    {"sla_tracking_id": tracking.id},
                )
                tracking.is_breached = True
                tracking.breach_sent = True
                results.append(
                    {
                        "entity_type": tracking.entity_type.value,
                        "entity_id": tracking.entity_id,
                        "event": "sla_breach",
                    }
                )

        await self.db.commit()
        return results


class SLAService:
    """Service for managing SLA tracking with business hours support."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_tracking(
        self,
        entity_type: EntityType,
        entity_id: int,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        department: Optional[str] = None,
        contract: Optional[str] = None,
    ) -> Optional[SLATracking]:
        """Start SLA tracking for an entity."""
        config = await self._find_matching_config(entity_type, priority, category, department, contract)
        if not config:
            logger.info(f"No SLA config found for {entity_type.value}")
            return None

        now = datetime.now(timezone.utc)

        acknowledgment_due = None
        response_due = None

        if config.acknowledgment_hours:
            acknowledgment_due = self._calculate_due_time(now, config.acknowledgment_hours, config)
        if config.response_hours:
            response_due = self._calculate_due_time(now, config.response_hours, config)

        resolution_due = self._calculate_due_time(now, config.resolution_hours, config)

        tracking = SLATracking(
            entity_type=entity_type,
            entity_id=entity_id,
            sla_config_id=config.id,
            started_at=now,
            acknowledgment_due=acknowledgment_due,
            response_due=response_due,
            resolution_due=resolution_due,
        )

        self.db.add(tracking)
        await self.db.commit()
        await self.db.refresh(tracking)
        return tracking

    async def mark_acknowledged(self, entity_type: EntityType, entity_id: int) -> Optional[SLATracking]:
        tracking = await self._get_tracking(entity_type, entity_id)
        if tracking and not tracking.acknowledged_at:
            tracking.acknowledged_at = datetime.now(timezone.utc)
            tracking.acknowledgment_met = (
                tracking.acknowledged_at <= tracking.acknowledgment_due if tracking.acknowledgment_due else True
            )
            await self.db.commit()
        return tracking

    async def mark_responded(self, entity_type: EntityType, entity_id: int) -> Optional[SLATracking]:
        tracking = await self._get_tracking(entity_type, entity_id)
        if tracking and not tracking.responded_at:
            tracking.responded_at = datetime.now(timezone.utc)
            tracking.response_met = tracking.responded_at <= tracking.response_due if tracking.response_due else True
            await self.db.commit()
        return tracking

    async def mark_resolved(self, entity_type: EntityType, entity_id: int) -> Optional[SLATracking]:
        tracking = await self._get_tracking(entity_type, entity_id)
        if tracking and not tracking.resolved_at:
            tracking.resolved_at = datetime.now(timezone.utc)
            tracking.resolution_met = tracking.resolved_at <= tracking.resolution_due
            await self.db.commit()
        return tracking

    async def pause_tracking(self, entity_type: EntityType, entity_id: int, reason: str = "") -> Optional[SLATracking]:
        tracking = await self._get_tracking(entity_type, entity_id)
        if tracking and not tracking.is_paused:
            tracking.is_paused = True
            tracking.paused_at = datetime.now(timezone.utc)
            await self.db.commit()
        return tracking

    async def resume_tracking(self, entity_type: EntityType, entity_id: int) -> Optional[SLATracking]:
        tracking = await self._get_tracking(entity_type, entity_id)
        if tracking and tracking.is_paused and tracking.paused_at is not None:
            paused_duration = (datetime.now(timezone.utc) - tracking.paused_at).total_seconds() / 3600
            tracking.total_paused_hours += paused_duration
            tracking.is_paused = False
            tracking.paused_at = None

            adjustment = timedelta(hours=paused_duration)
            if tracking.acknowledgment_due:
                tracking.acknowledgment_due += adjustment
            if tracking.response_due:
                tracking.response_due += adjustment
            tracking.resolution_due += adjustment

            await self.db.commit()
        return tracking

    async def _get_tracking(self, entity_type: EntityType, entity_id: int) -> Optional[SLATracking]:
        result = await self.db.execute(
            select(SLATracking)
            .where(
                and_(
                    SLATracking.entity_type == entity_type,
                    SLATracking.entity_id == entity_id,
                )
            )
            .order_by(SLATracking.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _find_matching_config(
        self,
        entity_type: EntityType,
        priority: Optional[str],
        category: Optional[str],
        department: Optional[str],
        contract: Optional[str],
    ) -> Optional[SLAConfiguration]:
        """Find the most specific matching SLA configuration."""
        query = (
            select(SLAConfiguration)
            .where(
                and_(
                    SLAConfiguration.entity_type == entity_type,
                    SLAConfiguration.is_active == True,
                )
            )
            .order_by(SLAConfiguration.match_priority.desc())
        )

        result = await self.db.execute(query)
        configs = result.scalars().all()

        for config in configs:
            matches = True
            if config.priority and config.priority != priority:
                matches = False
            if config.category and config.category != category:
                matches = False
            if config.department and config.department != department:
                matches = False
            if config.contract and config.contract != contract:
                matches = False
            if matches:
                return config

        return configs[0] if configs else None

    def _calculate_due_time(self, start: datetime, hours: float, config: SLAConfiguration) -> datetime:
        """Calculate due time considering business hours."""
        if not config.business_hours_only:
            return start + timedelta(hours=hours)

        biz_start: int = int(config.business_start_hour or 9)
        biz_end: int = int(config.business_end_hour or 17)

        current = start
        remaining_hours = hours

        while remaining_hours > 0:
            if current.hour < biz_start:
                current = current.replace(hour=biz_start, minute=0, second=0)
            elif current.hour >= biz_end:
                current = current + timedelta(days=1)
                current = current.replace(hour=biz_start, minute=0, second=0)

            if config.exclude_weekends and current.weekday() >= 5:
                days_until_monday = 7 - current.weekday()
                current = current + timedelta(days=days_until_monday)
                current = current.replace(hour=biz_start, minute=0, second=0)
                continue

            hours_today = biz_end - current.hour
            if remaining_hours <= hours_today:
                current = current + timedelta(hours=remaining_hours)
                remaining_hours = 0
            else:
                remaining_hours -= hours_today
                current = current + timedelta(days=1)
                current = current.replace(hour=biz_start, minute=0, second=0)

        return current


# ==================== In-Memory Workflow Service (from workflow_service) ====================


class EscalationRule(str, enum.Enum):
    """Escalation trigger rules."""

    TIME_BASED = "time_based"
    REJECTION_COUNT = "rejection_count"
    SEVERITY_LEVEL = "severity_level"


@dataclass
class WorkflowStepDef:
    """Definition of a single workflow step (in-memory)."""

    id: str
    name: str
    step_type: WorkflowStepType
    order: int
    assignee_role: Optional[str] = None
    assignee_user_id: Optional[str] = None
    timeout_hours: Optional[int] = None
    escalation_rule: Optional[EscalationRule] = None
    escalation_target: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, Any]]] = None
    parallel_steps: Optional[List["WorkflowStepDef"]] = None


@dataclass
class WorkflowDefinition:
    """Complete workflow template definition (in-memory)."""

    id: str
    name: str
    description: str
    module: str
    trigger_event: str
    steps: List[WorkflowStepDef]
    sla_hours: Optional[int] = None
    auto_escalate: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class WorkflowInstanceState:
    """Running instance of a workflow (in-memory)."""

    id: str
    definition_id: str
    entity_type: str
    entity_id: str
    status: WorkflowStatus
    current_step_index: int
    data: Dict[str, Any]
    history: List[Dict[str, Any]]
    started_at: datetime
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None


@dataclass
class ApprovalRequestState:
    """Approval request for a workflow step (in-memory)."""

    id: str
    workflow_instance_id: str
    step_id: str
    approver_id: str
    status: str
    requested_at: datetime
    responded_at: Optional[datetime] = None
    comments: Optional[str] = None


class WorkflowService:
    """In-memory workflow engine with approval routing and escalation."""

    def __init__(self):
        self._definitions: Dict[str, WorkflowDefinition] = {}
        self._instances: Dict[str, WorkflowInstanceState] = {}
        self._approvals: Dict[str, ApprovalRequestState] = {}
        self._initialize_default_workflows()

    def _initialize_default_workflows(self):
        """Initialize default workflow definitions."""
        incident_workflow = WorkflowDefinition(
            id="WF-INCIDENT-001",
            name="Incident Approval Workflow",
            description="Multi-level approval for high-severity incidents",
            module="incidents",
            trigger_event="incident.created",
            sla_hours=24,
            steps=[
                WorkflowStepDef(
                    id="STEP-001",
                    name="Initial Review",
                    step_type=WorkflowStepType.APPROVAL,
                    order=1,
                    assignee_role="supervisor",
                    timeout_hours=4,
                    escalation_rule=EscalationRule.TIME_BASED,
                    escalation_target="manager",
                ),
                WorkflowStepDef(
                    id="STEP-002",
                    name="Manager Approval",
                    step_type=WorkflowStepType.APPROVAL,
                    order=2,
                    assignee_role="manager",
                    timeout_hours=8,
                    conditions={"severity": ["high", "critical"]},
                ),
                WorkflowStepDef(
                    id="STEP-003",
                    name="Notify Stakeholders",
                    step_type=WorkflowStepType.NOTIFICATION,
                    order=3,
                    actions=[
                        {"type": "email", "template": "incident_approved"},
                        {"type": "push", "message": "Incident approved"},
                    ],
                ),
                WorkflowStepDef(
                    id="STEP-004",
                    name="Create Action Items",
                    step_type=WorkflowStepType.AUTOMATIC,
                    order=4,
                    actions=[{"type": "create_actions", "source": "investigation"}],
                ),
            ],
        )
        self._definitions[incident_workflow.id] = incident_workflow

        risk_workflow = WorkflowDefinition(
            id="WF-RISK-001",
            name="Risk Assessment Workflow",
            description="Risk review and approval process",
            module="risks",
            trigger_event="risk.created",
            sla_hours=48,
            steps=[
                WorkflowStepDef(
                    id="STEP-001",
                    name="Risk Owner Review",
                    step_type=WorkflowStepType.TASK,
                    order=1,
                    assignee_role="risk_owner",
                    timeout_hours=24,
                ),
                WorkflowStepDef(
                    id="STEP-002",
                    name="Mitigation Plan Approval",
                    step_type=WorkflowStepType.APPROVAL,
                    order=2,
                    assignee_role="risk_committee",
                    timeout_hours=24,
                ),
                WorkflowStepDef(
                    id="STEP-003",
                    name="Implementation Verification",
                    step_type=WorkflowStepType.APPROVAL,
                    order=3,
                    assignee_role="quality_manager",
                    timeout_hours=48,
                ),
            ],
        )
        self._definitions[risk_workflow.id] = risk_workflow

        doc_workflow = WorkflowDefinition(
            id="WF-DOC-001",
            name="Document Approval Workflow",
            description="Document review and publication process",
            module="documents",
            trigger_event="document.submitted",
            sla_hours=72,
            steps=[
                WorkflowStepDef(
                    id="STEP-001",
                    name="Author Self-Review",
                    step_type=WorkflowStepType.TASK,
                    order=1,
                    timeout_hours=4,
                ),
                WorkflowStepDef(
                    id="STEP-002",
                    name="Parallel Review",
                    step_type=WorkflowStepType.PARALLEL,
                    order=2,
                    timeout_hours=48,
                    parallel_steps=[
                        WorkflowStepDef(
                            id="STEP-002A",
                            name="Technical Review",
                            step_type=WorkflowStepType.APPROVAL,
                            order=1,
                            assignee_role="technical_reviewer",
                        ),
                        WorkflowStepDef(
                            id="STEP-002B",
                            name="Compliance Review",
                            step_type=WorkflowStepType.APPROVAL,
                            order=1,
                            assignee_role="compliance_officer",
                        ),
                    ],
                ),
                WorkflowStepDef(
                    id="STEP-003",
                    name="Final Approval",
                    step_type=WorkflowStepType.APPROVAL,
                    order=3,
                    assignee_role="document_controller",
                    timeout_hours=24,
                ),
                WorkflowStepDef(
                    id="STEP-004",
                    name="Publish Document",
                    step_type=WorkflowStepType.AUTOMATIC,
                    order=4,
                    actions=[
                        {"type": "update_status", "status": "published"},
                        {"type": "notify_subscribers"},
                    ],
                ),
            ],
        )
        self._definitions[doc_workflow.id] = doc_workflow

    async def get_workflow_definitions(self, module: Optional[str] = None) -> List[WorkflowDefinition]:
        """Get all workflow definitions, optionally filtered by module."""
        definitions = list(self._definitions.values())
        if module:
            definitions = [d for d in definitions if d.module == module]
        return definitions

    async def get_workflow_definition(self, definition_id: str) -> Optional[WorkflowDefinition]:
        """Get a specific workflow definition."""
        return self._definitions.get(definition_id)

    async def start_workflow(
        self,
        definition_id: str,
        entity_type: str,
        entity_id: str,
        data: Dict[str, Any],
        initiated_by: str,
    ) -> WorkflowInstanceState:
        """Start a new workflow instance."""
        definition = self._definitions.get(definition_id)
        if not definition:
            raise ValueError(f"Workflow definition {definition_id} not found")

        instance_id = f"WFI-{uuid4().hex[:8].upper()}"
        deadline = None
        if definition.sla_hours:
            deadline = datetime.now() + timedelta(hours=definition.sla_hours)

        instance = WorkflowInstanceState(
            id=instance_id,
            definition_id=definition_id,
            entity_type=entity_type,
            entity_id=entity_id,
            status=WorkflowStatus.IN_PROGRESS,
            current_step_index=0,
            data=data,
            history=[
                {
                    "action": "workflow_started",
                    "timestamp": datetime.now().isoformat(),
                    "user_id": initiated_by,
                    "details": {"definition": definition.name},
                }
            ],
            started_at=datetime.now(),
            deadline=deadline,
        )

        self._instances[instance_id] = instance
        logger.info(f"Started workflow instance {instance_id} for {entity_type}/{entity_id}")

        await self._process_current_step(instance)
        return instance

    async def _process_current_step(self, instance: WorkflowInstanceState) -> None:
        """Process the current step of a workflow instance."""
        definition = self._definitions[instance.definition_id]
        if instance.current_step_index >= len(definition.steps):
            await self._complete_workflow(instance)
            return

        step = definition.steps[instance.current_step_index]

        if step.conditions and not self._evaluate_conditions(step.conditions, instance.data):
            instance.history.append(
                {
                    "action": "step_skipped",
                    "step_id": step.id,
                    "timestamp": datetime.now().isoformat(),
                    "reason": "conditions_not_met",
                }
            )
            instance.current_step_index += 1
            await self._process_current_step(instance)
            return

        if step.step_type == WorkflowStepType.APPROVAL:
            instance.status = WorkflowStatus.AWAITING_APPROVAL
            await self._create_approval_request(instance, step)

        elif step.step_type == WorkflowStepType.NOTIFICATION:
            await self._send_notifications(instance, step)
            instance.current_step_index += 1
            await self._process_current_step(instance)

        elif step.step_type == WorkflowStepType.AUTOMATIC:
            await self._execute_automatic_actions(instance, step)
            instance.current_step_index += 1
            await self._process_current_step(instance)

        elif step.step_type == WorkflowStepType.TASK:
            instance.status = WorkflowStatus.IN_PROGRESS

        elif step.step_type == WorkflowStepType.PARALLEL:
            await self._process_parallel_steps(instance, step)

    def _evaluate_conditions(self, conditions: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """Evaluate step conditions against workflow data."""
        for key, expected_values in conditions.items():
            actual_value = data.get(key)
            if isinstance(expected_values, list):
                if actual_value not in expected_values:
                    return False
            elif actual_value != expected_values:
                return False
        return True

    async def _create_approval_request(
        self, instance: WorkflowInstanceState, step: WorkflowStepDef
    ) -> ApprovalRequestState:
        """Create an approval request for a workflow step."""
        request_id = f"APR-{uuid4().hex[:8].upper()}"
        approver_id = step.assignee_user_id or f"role:{step.assignee_role}"

        request = ApprovalRequestState(
            id=request_id,
            workflow_instance_id=instance.id,
            step_id=step.id,
            approver_id=approver_id,
            status="pending",
            requested_at=datetime.now(),
        )

        self._approvals[request_id] = request

        instance.history.append(
            {
                "action": "approval_requested",
                "step_id": step.id,
                "timestamp": datetime.now().isoformat(),
                "approver": approver_id,
                "request_id": request_id,
            }
        )

        logger.info(f"Created approval request {request_id} for step {step.name}")
        return request

    async def approve_step(
        self, request_id: str, approver_id: str, comments: Optional[str] = None
    ) -> WorkflowInstanceState:
        """Approve a workflow step."""
        request = self._approvals.get(request_id)
        if not request:
            raise ValueError(f"Approval request {request_id} not found")

        if request.status != "pending":
            raise ValueError(f"Approval request already {request.status}")

        request.status = "approved"
        request.responded_at = datetime.now()
        request.comments = comments

        instance = self._instances[request.workflow_instance_id]
        instance.history.append(
            {
                "action": "step_approved",
                "step_id": request.step_id,
                "timestamp": datetime.now().isoformat(),
                "approver": approver_id,
                "comments": comments,
            }
        )

        instance.current_step_index += 1
        instance.status = WorkflowStatus.IN_PROGRESS
        await self._process_current_step(instance)
        return instance

    async def reject_step(self, request_id: str, rejector_id: str, reason: str) -> WorkflowInstanceState:
        """Reject a workflow step."""
        request = self._approvals.get(request_id)
        if not request:
            raise ValueError(f"Approval request {request_id} not found")

        request.status = "rejected"
        request.responded_at = datetime.now()
        request.comments = reason

        instance = self._instances[request.workflow_instance_id]
        instance.status = WorkflowStatus.REJECTED
        instance.history.append(
            {
                "action": "step_rejected",
                "step_id": request.step_id,
                "timestamp": datetime.now().isoformat(),
                "rejector": rejector_id,
                "reason": reason,
            }
        )

        logger.info(f"Workflow {instance.id} rejected at step {request.step_id}")
        return instance

    async def _send_notifications(self, instance: WorkflowInstanceState, step: WorkflowStepDef) -> None:
        """Send notifications for a workflow step."""
        if not step.actions:
            return

        for action in step.actions:
            action_type = action.get("type")
            if action_type == "email":
                logger.info(f"Sending email notification for workflow {instance.id}: {action.get('template')}")
            elif action_type == "push":
                logger.info(f"Sending push notification for workflow {instance.id}: {action.get('message')}")

        instance.history.append(
            {
                "action": "notifications_sent",
                "step_id": step.id,
                "timestamp": datetime.now().isoformat(),
                "notification_count": len(step.actions),
            }
        )

    async def _execute_automatic_actions(self, instance: WorkflowInstanceState, step: WorkflowStepDef) -> None:
        """Execute automatic actions for a workflow step."""
        if not step.actions:
            return

        for action in step.actions:
            action_type = action.get("type")
            logger.info(f"Executing automatic action '{action_type}' for workflow {instance.id}")

        instance.history.append(
            {
                "action": "automatic_actions_executed",
                "step_id": step.id,
                "timestamp": datetime.now().isoformat(),
                "actions": [a.get("type") for a in step.actions],
            }
        )

    async def _process_parallel_steps(self, instance: WorkflowInstanceState, step: WorkflowStepDef) -> None:
        """Process parallel workflow steps."""
        if not step.parallel_steps:
            return

        for parallel_step in step.parallel_steps:
            if parallel_step.step_type == WorkflowStepType.APPROVAL:
                await self._create_approval_request(instance, parallel_step)

        instance.history.append(
            {
                "action": "parallel_steps_started",
                "step_id": step.id,
                "timestamp": datetime.now().isoformat(),
                "parallel_count": len(step.parallel_steps),
            }
        )

    async def _complete_workflow(self, instance: WorkflowInstanceState) -> None:
        """Mark a workflow as completed."""
        instance.status = WorkflowStatus.COMPLETED
        instance.completed_at = datetime.now()
        instance.history.append({"action": "workflow_completed", "timestamp": datetime.now().isoformat()})
        logger.info(f"Workflow {instance.id} completed successfully")

    async def get_workflow_instance(self, instance_id: str) -> Optional[WorkflowInstanceState]:
        """Get a workflow instance by ID."""
        return self._instances.get(instance_id)

    async def get_pending_approvals(self, user_id: str) -> List[ApprovalRequestState]:
        """Get all pending approval requests for a user."""
        return [
            a
            for a in self._approvals.values()
            if a.status == "pending" and (a.approver_id == user_id or a.approver_id.endswith(user_id))
        ]

    async def get_workflow_stats(self) -> Dict[str, Any]:
        """Get workflow statistics."""
        instances = list(self._instances.values())
        return {
            "total_workflows": len(instances),
            "active": len([i for i in instances if i.status == WorkflowStatus.IN_PROGRESS]),
            "awaiting_approval": len([i for i in instances if i.status == WorkflowStatus.AWAITING_APPROVAL]),
            "completed": len([i for i in instances if i.status == WorkflowStatus.COMPLETED]),
            "rejected": len([i for i in instances if i.status == WorkflowStatus.REJECTED]),
            "pending_approvals": len([a for a in self._approvals.values() if a.status == "pending"]),
        }


# Singleton instance for in-memory workflows
workflow_service = WorkflowService()
