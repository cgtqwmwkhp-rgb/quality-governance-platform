from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ============================================================================
# Existing schemas (preserved)
# ============================================================================


class WorkflowTemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    steps: list[dict[str, Any]] = []

    class Config:
        from_attributes = True


class WorkflowInstanceResponse(BaseModel):
    id: int
    template_id: int
    status: str
    current_step: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApprovalResponse(BaseModel):
    id: int
    status: str
    approved_by: Optional[int] = None
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class DelegationResponse(BaseModel):
    id: int
    delegated_by: int
    delegated_to: int
    active: bool = True

    class Config:
        from_attributes = True


class WorkflowStatsResponse(BaseModel):
    total_workflows: int = 0
    active_workflows: int = 0
    completed_workflows: int = 0
    pending_approvals: int = 0


# ============================================================================
# Template endpoint responses
# ============================================================================


class TemplateSummaryItem(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    trigger_entity_type: Optional[str] = None
    sla_hours: Optional[int] = None
    steps_count: int = 0


class ListTemplatesResponse(BaseModel):
    templates: List[TemplateSummaryItem]


class GetTemplateResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    trigger_entity_type: Optional[str] = None
    trigger_conditions: Any = None
    sla_hours: Optional[int] = None
    warning_hours: Optional[int] = None
    steps: Any = None
    escalation_rules: Any = None
    is_active: bool = True
    version: Optional[int] = None


# ============================================================================
# Instance endpoint responses
# ============================================================================


class StartWorkflowResponse(BaseModel):
    id: int
    template_id: int
    entity_type: str
    entity_id: str
    status: str
    priority: str
    current_step: Optional[int] = None
    current_step_name: Optional[str] = None
    total_steps: int = 0
    sla_due_at: Optional[str] = None
    started_at: Optional[str] = None


class InstanceListItem(BaseModel):
    id: int
    template_id: int
    entity_type: str
    entity_id: str
    status: str
    priority: str
    current_step: str = ""
    progress: int = 0
    sla_status: str = "ok"
    started_at: Optional[str] = None


class ListInstancesResponse(BaseModel):
    items: List[InstanceListItem]
    total: int


class StepDetail(BaseModel):
    id: int
    step_number: int
    name: Optional[str] = None
    type: Optional[str] = None
    status: str
    approval_type: Optional[str] = None
    required_approvers: Optional[int] = None
    outcome: Optional[str] = None
    outcome_reason: Optional[str] = None
    outcome_by: Optional[int] = None
    due_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class GetInstanceResponse(BaseModel):
    id: int
    template_id: int
    entity_type: str
    entity_id: str
    status: str
    priority: str
    current_step: Optional[int] = None
    current_step_name: Optional[str] = None
    total_steps: int = 0
    progress: int = 0
    sla_due_at: Optional[str] = None
    sla_status: str = "ok"
    initiated_by: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    context: Any = None
    steps: List[StepDetail] = []


class AdvanceWorkflowResponse(BaseModel):
    workflow_id: int
    action: str
    outcome: str
    outcome_by: int
    notes: Optional[str] = None
    next_step: Optional[str] = None
    status: str
    timestamp: str


class CancelWorkflowResponse(BaseModel):
    workflow_id: int
    status: str
    cancelled_by: int
    reason: Optional[str] = None
    timestamp: str


# ============================================================================
# Approval endpoint responses
# ============================================================================


class PendingApprovalItem(BaseModel):
    id: int
    workflow_id: int
    workflow_name: str
    step_name: Optional[str] = None
    entity_type: str
    entity_id: str
    entity_title: str
    requested_at: str
    due_at: Optional[str] = None
    priority: str
    sla_status: str = "ok"


class ListPendingApprovalsResponse(BaseModel):
    approvals: List[PendingApprovalItem]
    total: int


class ApproveStepResponse(BaseModel):
    """Returned by approve_step / advance_workflow engine call."""

    workflow_id: int
    action: str
    outcome: str
    outcome_by: int
    notes: Optional[str] = None
    next_step: Optional[str] = None
    status: str
    timestamp: str


class RejectStepResponse(BaseModel):
    workflow_id: int
    step_id: int
    action: str
    rejected_by: int
    reason: str
    timestamp: str


class BulkApproveResponse(BaseModel):
    processed: int
    successful: int
    failed: int
    results: List[Any] = []
    errors: List[Any] = []


# ============================================================================
# Escalation endpoint responses
# ============================================================================


class EscalationItem(BaseModel):
    workflow_id: int
    template: str
    reason: str
    hours_overdue: int
    current_step: Optional[str] = None
    recommended_action: str


class ListPendingEscalationsResponse(BaseModel):
    escalations: List[EscalationItem]
    total: int


class EscalateWorkflowResponse(BaseModel):
    workflow_id: int
    escalated_by: int
    reason: str
    new_priority: str
    escalated_at: str


# ============================================================================
# Delegation endpoint responses
# ============================================================================


class DelegationItem(BaseModel):
    id: int
    delegate_id: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    reason: Optional[str] = None
    is_active: bool = True


class ListDelegationsResponse(BaseModel):
    delegations: List[DelegationItem]


class CreateDelegationResponse(BaseModel):
    id: int
    user_id: int
    delegate_id: int
    start_date: str
    end_date: str
    reason: Optional[str] = None
    status: str


class CancelDelegationResponse(BaseModel):
    delegation_id: int
    status: str
    cancelled_at: str


# ============================================================================
# Statistics endpoint response
# ============================================================================


class GetWorkflowStatsResponse(BaseModel):
    active_workflows: int = 0
    pending_approvals: int = 0
    overdue: int = 0
    completed_today: int = 0
    completed_this_week: int = 0
    by_status: Dict[str, int] = {}
    by_priority: Dict[str, int] = {}
