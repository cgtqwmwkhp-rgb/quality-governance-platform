"""Workflow Engine API Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# Enums as string literals for API
class RuleTypeEnum:
    CONDITIONAL_TRIGGER = "conditional_trigger"
    ESCALATION = "escalation"
    AUTO_ASSIGNMENT = "auto_assignment"
    SLA_MONITOR = "sla_monitor"
    NOTIFICATION = "notification"


class EntityTypeEnum:
    INCIDENT = "incident"
    NEAR_MISS = "near_miss"
    COMPLAINT = "complaint"
    RTA = "rta"
    AUDIT = "audit"
    RISK = "risk"
    INVESTIGATION = "investigation"
    POLICY = "policy"
    FINDING = "finding"
    ACTION = "action"


# Workflow Rule Schemas
class WorkflowRuleBase(BaseModel):
    """Base schema for workflow rules."""

    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    rule_type: str = Field(
        ...,
        description="Type: conditional_trigger, escalation, auto_assignment, sla_monitor, notification",
    )
    entity_type: str = Field(
        ...,
        description="Entity: incident, near_miss, complaint, rta, audit, risk, etc.",
    )
    trigger_event: str = Field(
        ..., description="Event: created, updated, status_changed, sla_breach, etc."
    )
    conditions: Optional[Dict[str, Any]] = Field(
        None, description="Condition JSON for rule evaluation"
    )
    delay_hours: Optional[float] = Field(
        None, description="Hours to wait before executing (for escalation)"
    )
    delay_from_field: Optional[str] = Field(
        None, description="Field to calculate delay from"
    )
    action_type: str = Field(
        ...,
        description="Action: send_email, assign_to_user, change_status, escalate, etc.",
    )
    action_config: Dict[str, Any] = Field(
        ..., description="Configuration for the action"
    )
    priority: int = Field(100, description="Rule priority (lower = higher priority)")
    stop_processing: bool = Field(
        False, description="Stop processing rules after this one"
    )
    is_active: bool = True
    department: Optional[str] = None
    contract: Optional[str] = None


class WorkflowRuleCreate(WorkflowRuleBase):
    """Schema for creating a workflow rule."""

    pass


class WorkflowRuleUpdate(BaseModel):
    """Schema for updating a workflow rule."""

    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    rule_type: Optional[str] = None
    entity_type: Optional[str] = None
    trigger_event: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    delay_hours: Optional[float] = None
    delay_from_field: Optional[str] = None
    action_type: Optional[str] = None
    action_config: Optional[Dict[str, Any]] = None
    priority: Optional[int] = None
    stop_processing: Optional[bool] = None
    is_active: Optional[bool] = None
    department: Optional[str] = None
    contract: Optional[str] = None


class WorkflowRuleResponse(WorkflowRuleBase):
    """Schema for workflow rule response."""

    id: int
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None

    class Config:
        from_attributes = True


class WorkflowRuleListResponse(BaseModel):
    """List response for workflow rules."""

    items: List[WorkflowRuleResponse]
    total: int
    page: int
    page_size: int


# Rule Execution Schemas
class RuleExecutionResponse(BaseModel):
    """Schema for rule execution log entry."""

    id: int
    rule_id: int
    entity_type: str
    entity_id: int
    trigger_event: str
    executed_at: datetime
    success: bool
    error_message: Optional[str] = None
    action_taken: Optional[str] = None
    action_result: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class RuleExecutionListResponse(BaseModel):
    """List response for rule executions."""

    items: List[RuleExecutionResponse]
    total: int


# SLA Configuration Schemas
class SLAConfigurationBase(BaseModel):
    """Base schema for SLA configurations."""

    entity_type: str = Field(..., description="Entity type this SLA applies to")
    priority: Optional[str] = Field(
        None, description="Priority level (critical, high, medium, low)"
    )
    category: Optional[str] = Field(
        None, description="Category (incident type, complaint type, etc.)"
    )
    department: Optional[str] = None
    contract: Optional[str] = None
    acknowledgment_hours: Optional[float] = Field(
        None, description="Hours to acknowledge"
    )
    response_hours: Optional[float] = Field(None, description="Hours to first response")
    resolution_hours: float = Field(..., description="Hours to resolution")
    warning_threshold_percent: int = Field(
        75, description="Percentage of SLA for warning"
    )
    business_hours_only: bool = Field(
        True, description="Calculate using business hours only"
    )
    business_start_hour: int = Field(9, ge=0, le=23)
    business_end_hour: int = Field(17, ge=0, le=23)
    exclude_weekends: bool = True
    is_active: bool = True
    match_priority: int = Field(
        0, description="Higher = more specific, evaluated first"
    )


class SLAConfigurationCreate(SLAConfigurationBase):
    """Schema for creating an SLA configuration."""

    pass


class SLAConfigurationUpdate(BaseModel):
    """Schema for updating an SLA configuration."""

    priority: Optional[str] = None
    category: Optional[str] = None
    department: Optional[str] = None
    contract: Optional[str] = None
    acknowledgment_hours: Optional[float] = None
    response_hours: Optional[float] = None
    resolution_hours: Optional[float] = None
    warning_threshold_percent: Optional[int] = None
    business_hours_only: Optional[bool] = None
    business_start_hour: Optional[int] = None
    business_end_hour: Optional[int] = None
    exclude_weekends: Optional[bool] = None
    is_active: Optional[bool] = None
    match_priority: Optional[int] = None


class SLAConfigurationResponse(SLAConfigurationBase):
    """Schema for SLA configuration response."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SLAConfigurationListResponse(BaseModel):
    """List response for SLA configurations."""

    items: List[SLAConfigurationResponse]
    total: int


# SLA Tracking Schemas
class SLATrackingResponse(BaseModel):
    """Schema for SLA tracking status."""

    id: int
    entity_type: str
    entity_id: int
    sla_config_id: int
    started_at: datetime
    acknowledged_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledgment_due: Optional[datetime] = None
    response_due: Optional[datetime] = None
    resolution_due: datetime
    acknowledgment_met: Optional[bool] = None
    response_met: Optional[bool] = None
    resolution_met: Optional[bool] = None
    warning_sent: bool
    breach_sent: bool
    is_breached: bool
    is_paused: bool
    total_paused_hours: float

    class Config:
        from_attributes = True


class SLAStatusSummary(BaseModel):
    """Summary of SLA status for an entity."""

    entity_type: str
    entity_id: int
    status: str  # on_track, warning, breached, resolved
    percent_elapsed: float
    time_remaining_hours: Optional[float]
    resolution_due: datetime
    is_paused: bool


# Escalation Level Schemas
class EscalationLevelBase(BaseModel):
    """Base schema for escalation levels."""

    entity_type: str = Field(..., description="Entity type this level applies to")
    level: int = Field(..., ge=1, description="Escalation level (1 = first)")
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    escalate_to_role: Optional[str] = None
    escalate_to_user_id: Optional[int] = None
    notification_template: Optional[str] = None
    notify_original_assignee: bool = True
    notify_reporter: bool = False
    hours_after_previous: float = Field(..., description="Hours after previous level")
    is_active: bool = True


class EscalationLevelCreate(EscalationLevelBase):
    """Schema for creating an escalation level."""

    pass


class EscalationLevelUpdate(BaseModel):
    """Schema for updating an escalation level."""

    name: Optional[str] = None
    description: Optional[str] = None
    escalate_to_role: Optional[str] = None
    escalate_to_user_id: Optional[int] = None
    notification_template: Optional[str] = None
    notify_original_assignee: Optional[bool] = None
    notify_reporter: Optional[bool] = None
    hours_after_previous: Optional[float] = None
    is_active: Optional[bool] = None


class EscalationLevelResponse(EscalationLevelBase):
    """Schema for escalation level response."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EscalationLevelListResponse(BaseModel):
    """List response for escalation levels."""

    items: List[EscalationLevelResponse]
    total: int


# Condition Builder Helper Schema
class ConditionSchema(BaseModel):
    """Schema for a single condition."""

    field: str = Field(..., description="Field name to evaluate")
    operator: str = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Value to compare against")


class ConditionGroupSchema(BaseModel):
    """Schema for grouped conditions."""

    and_conditions: Optional[List["ConditionSchema"]] = Field(None, alias="and")
    or_conditions: Optional[List["ConditionSchema"]] = Field(None, alias="or")
    not_condition: Optional["ConditionSchema"] = Field(None, alias="not")
