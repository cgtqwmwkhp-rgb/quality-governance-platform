"""
Workflow Service - Enterprise Workflow Engine

Provides multi-step workflow management, approval routing, escalation rules,
and automated actions for the Quality Governance Platform.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from uuid import uuid4

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Workflow instance status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StepType(str, Enum):
    """Types of workflow steps."""

    APPROVAL = "approval"
    NOTIFICATION = "notification"
    TASK = "task"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"
    AUTOMATIC = "automatic"


class EscalationRule(str, Enum):
    """Escalation trigger rules."""

    TIME_BASED = "time_based"
    REJECTION_COUNT = "rejection_count"
    SEVERITY_LEVEL = "severity_level"


@dataclass
class WorkflowStep:
    """Definition of a single workflow step."""

    id: str
    name: str
    step_type: StepType
    order: int
    assignee_role: Optional[str] = None
    assignee_user_id: Optional[str] = None
    timeout_hours: Optional[int] = None
    escalation_rule: Optional[EscalationRule] = None
    escalation_target: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, Any]]] = None
    parallel_steps: Optional[List["WorkflowStep"]] = None


@dataclass
class WorkflowDefinition:
    """Complete workflow template definition."""

    id: str
    name: str
    description: str
    module: str
    trigger_event: str
    steps: List[WorkflowStep]
    sla_hours: Optional[int] = None
    auto_escalate: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class WorkflowInstance:
    """Running instance of a workflow."""

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
class ApprovalRequest:
    """Approval request for a workflow step."""

    id: str
    workflow_instance_id: str
    step_id: str
    approver_id: str
    status: str  # pending, approved, rejected
    requested_at: datetime
    responded_at: Optional[datetime] = None
    comments: Optional[str] = None


class WorkflowService:
    """Enterprise workflow engine with approval routing and escalation."""

    def __init__(self):
        # In-memory storage (replace with database in production)
        self._definitions: Dict[str, WorkflowDefinition] = {}
        self._instances: Dict[str, WorkflowInstance] = {}
        self._approvals: Dict[str, ApprovalRequest] = {}
        self._initialize_default_workflows()

    def _initialize_default_workflows(self):
        """Initialize default workflow definitions."""
        # Incident Approval Workflow
        incident_workflow = WorkflowDefinition(
            id="WF-INCIDENT-001",
            name="Incident Approval Workflow",
            description="Multi-level approval for high-severity incidents",
            module="incidents",
            trigger_event="incident.created",
            sla_hours=24,
            steps=[
                WorkflowStep(
                    id="STEP-001",
                    name="Initial Review",
                    step_type=StepType.APPROVAL,
                    order=1,
                    assignee_role="supervisor",
                    timeout_hours=4,
                    escalation_rule=EscalationRule.TIME_BASED,
                    escalation_target="manager",
                ),
                WorkflowStep(
                    id="STEP-002",
                    name="Manager Approval",
                    step_type=StepType.APPROVAL,
                    order=2,
                    assignee_role="manager",
                    timeout_hours=8,
                    conditions={"severity": ["high", "critical"]},
                ),
                WorkflowStep(
                    id="STEP-003",
                    name="Notify Stakeholders",
                    step_type=StepType.NOTIFICATION,
                    order=3,
                    actions=[
                        {"type": "email", "template": "incident_approved"},
                        {"type": "push", "message": "Incident approved"},
                    ],
                ),
                WorkflowStep(
                    id="STEP-004",
                    name="Create Action Items",
                    step_type=StepType.AUTOMATIC,
                    order=4,
                    actions=[{"type": "create_actions", "source": "investigation"}],
                ),
            ],
        )
        self._definitions[incident_workflow.id] = incident_workflow

        # Risk Assessment Workflow
        risk_workflow = WorkflowDefinition(
            id="WF-RISK-001",
            name="Risk Assessment Workflow",
            description="Risk review and approval process",
            module="risks",
            trigger_event="risk.created",
            sla_hours=48,
            steps=[
                WorkflowStep(
                    id="STEP-001",
                    name="Risk Owner Review",
                    step_type=StepType.TASK,
                    order=1,
                    assignee_role="risk_owner",
                    timeout_hours=24,
                ),
                WorkflowStep(
                    id="STEP-002",
                    name="Mitigation Plan Approval",
                    step_type=StepType.APPROVAL,
                    order=2,
                    assignee_role="risk_committee",
                    timeout_hours=24,
                ),
                WorkflowStep(
                    id="STEP-003",
                    name="Implementation Verification",
                    step_type=StepType.APPROVAL,
                    order=3,
                    assignee_role="quality_manager",
                    timeout_hours=48,
                ),
            ],
        )
        self._definitions[risk_workflow.id] = risk_workflow

        # Document Approval Workflow
        doc_workflow = WorkflowDefinition(
            id="WF-DOC-001",
            name="Document Approval Workflow",
            description="Document review and publication process",
            module="documents",
            trigger_event="document.submitted",
            sla_hours=72,
            steps=[
                WorkflowStep(
                    id="STEP-001",
                    name="Author Self-Review",
                    step_type=StepType.TASK,
                    order=1,
                    timeout_hours=4,
                ),
                WorkflowStep(
                    id="STEP-002",
                    name="Parallel Review",
                    step_type=StepType.PARALLEL,
                    order=2,
                    timeout_hours=48,
                    parallel_steps=[
                        WorkflowStep(
                            id="STEP-002A",
                            name="Technical Review",
                            step_type=StepType.APPROVAL,
                            order=1,
                            assignee_role="technical_reviewer",
                        ),
                        WorkflowStep(
                            id="STEP-002B",
                            name="Compliance Review",
                            step_type=StepType.APPROVAL,
                            order=1,
                            assignee_role="compliance_officer",
                        ),
                    ],
                ),
                WorkflowStep(
                    id="STEP-003",
                    name="Final Approval",
                    step_type=StepType.APPROVAL,
                    order=3,
                    assignee_role="document_controller",
                    timeout_hours=24,
                ),
                WorkflowStep(
                    id="STEP-004",
                    name="Publish Document",
                    step_type=StepType.AUTOMATIC,
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
    ) -> WorkflowInstance:
        """
        Start a new workflow instance.

        Args:
            definition_id: ID of the workflow definition to use
            entity_type: Type of entity (e.g., 'incident', 'risk')
            entity_id: ID of the entity
            data: Initial workflow data
            initiated_by: User ID who initiated the workflow

        Returns:
            Created workflow instance
        """
        definition = self._definitions.get(definition_id)
        if not definition:
            raise ValueError(f"Workflow definition {definition_id} not found")

        instance_id = f"WFI-{uuid4().hex[:8].upper()}"
        deadline = None
        if definition.sla_hours:
            deadline = datetime.now() + timedelta(hours=definition.sla_hours)

        instance = WorkflowInstance(
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

        # Process first step
        await self._process_current_step(instance)

        return instance

    async def _process_current_step(self, instance: WorkflowInstance) -> None:
        """Process the current step of a workflow instance."""
        definition = self._definitions[instance.definition_id]
        if instance.current_step_index >= len(definition.steps):
            # Workflow completed
            await self._complete_workflow(instance)
            return

        step = definition.steps[instance.current_step_index]

        # Check conditions
        if step.conditions and not self._evaluate_conditions(step.conditions, instance.data):
            # Skip this step
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

        # Handle different step types
        if step.step_type == StepType.APPROVAL:
            instance.status = WorkflowStatus.AWAITING_APPROVAL
            await self._create_approval_request(instance, step)

        elif step.step_type == StepType.NOTIFICATION:
            await self._send_notifications(instance, step)
            instance.current_step_index += 1
            await self._process_current_step(instance)

        elif step.step_type == StepType.AUTOMATIC:
            await self._execute_automatic_actions(instance, step)
            instance.current_step_index += 1
            await self._process_current_step(instance)

        elif step.step_type == StepType.TASK:
            instance.status = WorkflowStatus.IN_PROGRESS
            # Task awaits manual completion

        elif step.step_type == StepType.PARALLEL:
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

    async def _create_approval_request(self, instance: WorkflowInstance, step: WorkflowStep) -> ApprovalRequest:
        """Create an approval request for a workflow step."""
        request_id = f"APR-{uuid4().hex[:8].upper()}"

        # Determine approver (simplified - in production, lookup by role)
        approver_id = step.assignee_user_id or f"role:{step.assignee_role}"

        request = ApprovalRequest(
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

    async def approve_step(self, request_id: str, approver_id: str, comments: Optional[str] = None) -> WorkflowInstance:
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

        # Move to next step
        instance.current_step_index += 1
        instance.status = WorkflowStatus.IN_PROGRESS
        await self._process_current_step(instance)

        return instance

    async def reject_step(self, request_id: str, rejector_id: str, reason: str) -> WorkflowInstance:
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

    async def _send_notifications(self, instance: WorkflowInstance, step: WorkflowStep) -> None:
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

    async def _execute_automatic_actions(self, instance: WorkflowInstance, step: WorkflowStep) -> None:
        """Execute automatic actions for a workflow step."""
        if not step.actions:
            return

        for action in step.actions:
            action_type = action.get("type")
            logger.info(f"Executing automatic action '{action_type}' for workflow {instance.id}")
            # In production, dispatch to action handlers

        instance.history.append(
            {
                "action": "automatic_actions_executed",
                "step_id": step.id,
                "timestamp": datetime.now().isoformat(),
                "actions": [a.get("type") for a in step.actions],
            }
        )

    async def _process_parallel_steps(self, instance: WorkflowInstance, step: WorkflowStep) -> None:
        """Process parallel workflow steps."""
        if not step.parallel_steps:
            return

        for parallel_step in step.parallel_steps:
            if parallel_step.step_type == StepType.APPROVAL:
                await self._create_approval_request(instance, parallel_step)

        instance.history.append(
            {
                "action": "parallel_steps_started",
                "step_id": step.id,
                "timestamp": datetime.now().isoformat(),
                "parallel_count": len(step.parallel_steps),
            }
        )

    async def _complete_workflow(self, instance: WorkflowInstance) -> None:
        """Mark a workflow as completed."""
        instance.status = WorkflowStatus.COMPLETED
        instance.completed_at = datetime.now()
        instance.history.append(
            {
                "action": "workflow_completed",
                "timestamp": datetime.now().isoformat(),
            }
        )
        logger.info(f"Workflow {instance.id} completed successfully")

    async def get_workflow_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """Get a workflow instance by ID."""
        return self._instances.get(instance_id)

    async def get_pending_approvals(self, user_id: str) -> List[ApprovalRequest]:
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


# Singleton instance
workflow_service = WorkflowService()
