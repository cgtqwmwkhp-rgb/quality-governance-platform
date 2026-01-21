"""Workflow Rules Engine Models.

Provides conditional triggers, escalation timers, auto-assignment rules,
and SLA monitoring capabilities across all modules.
"""

import enum
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, TimestampMixin
from src.infrastructure.database import Base


class RuleType(str, enum.Enum):
    """Type of workflow rule."""
    CONDITIONAL_TRIGGER = "conditional_trigger"  # If X then Y
    ESCALATION = "escalation"  # After N hours/days, escalate
    AUTO_ASSIGNMENT = "auto_assignment"  # Assign based on criteria
    SLA_MONITOR = "sla_monitor"  # Track SLA compliance
    NOTIFICATION = "notification"  # Send notification on event


class EntityType(str, enum.Enum):
    """Entity types that rules can apply to."""
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


class TriggerEvent(str, enum.Enum):
    """Events that can trigger rules."""
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    DUE_DATE_APPROACHING = "due_date_approaching"
    DUE_DATE_PASSED = "due_date_passed"
    SLA_WARNING = "sla_warning"  # 75% of SLA elapsed
    SLA_BREACH = "sla_breach"  # SLA exceeded
    SEVERITY_HIGH = "severity_high"
    ESCALATED = "escalated"
    CLOSED = "closed"


class ActionType(str, enum.Enum):
    """Actions that rules can perform."""
    SEND_EMAIL = "send_email"
    SEND_SMS = "send_sms"
    ASSIGN_TO_USER = "assign_to_user"
    ASSIGN_TO_ROLE = "assign_to_role"
    CHANGE_STATUS = "change_status"
    CHANGE_PRIORITY = "change_priority"
    CREATE_TASK = "create_task"
    ESCALATE = "escalate"
    UPDATE_RISK_SCORE = "update_risk_score"
    LOG_AUDIT_EVENT = "log_audit_event"
    WEBHOOK = "webhook"


class WorkflowRule(Base, TimestampMixin, AuditTrailMixin):
    """Workflow rule definition for automation."""
    
    __tablename__ = "workflow_rules"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Rule identification
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_type: Mapped[RuleType] = mapped_column(SQLEnum(RuleType, native_enum=False), nullable=False)
    
    # Applies to which entities
    entity_type: Mapped[EntityType] = mapped_column(SQLEnum(EntityType, native_enum=False), nullable=False, index=True)
    
    # Trigger conditions
    trigger_event: Mapped[TriggerEvent] = mapped_column(SQLEnum(TriggerEvent, native_enum=False), nullable=False)
    
    # Condition JSON - evaluated to determine if rule fires
    # Example: {"field": "severity", "operator": "equals", "value": "critical"}
    # Complex: {"and": [{"field": "status", "operator": "equals", "value": "reported"}, {"field": "severity", "operator": "in", "value": ["critical", "high"]}]}
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # For escalation rules - time delay before action
    delay_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delay_from_field: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "created_at", "due_date"
    
    # Action to perform
    action_type: Mapped[ActionType] = mapped_column(SQLEnum(ActionType, native_enum=False), nullable=False)
    
    # Action configuration JSON
    # For email: {"template": "escalation", "recipients": ["manager"], "subject": "..."}
    # For assign: {"user_id": 123} or {"role": "safety_manager", "department": "from_entity"}
    # For status change: {"new_status": "escalated"}
    action_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Priority and ordering
    priority: Mapped[int] = mapped_column(Integer, default=100)  # Lower = higher priority
    stop_processing: Mapped[bool] = mapped_column(Boolean, default=False)  # Stop after this rule
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Scope limiting (optional)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contract: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Relationships
    executions: Mapped[List["RuleExecution"]] = relationship(
        "RuleExecution", back_populates="rule", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<WorkflowRule(id={self.id}, name='{self.name}', type={self.rule_type})>"


class RuleExecution(Base, TimestampMixin):
    """Log of rule executions for audit and debugging."""
    
    __tablename__ = "rule_executions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("workflow_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # What triggered this execution
    entity_type: Mapped[EntityType] = mapped_column(SQLEnum(EntityType, native_enum=False), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    trigger_event: Mapped[TriggerEvent] = mapped_column(SQLEnum(TriggerEvent, native_enum=False), nullable=False)
    
    # Execution result
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Action taken
    action_taken: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Human-readable description
    action_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Detailed result
    
    # Relationships
    rule: Mapped["WorkflowRule"] = relationship("WorkflowRule", back_populates="executions")
    
    def __repr__(self) -> str:
        return f"<RuleExecution(id={self.id}, rule_id={self.rule_id}, success={self.success})>"


class SLAConfiguration(Base, TimestampMixin, AuditTrailMixin):
    """SLA configuration for different entity types and priorities."""
    
    __tablename__ = "sla_configurations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # What this SLA applies to
    entity_type: Mapped[EntityType] = mapped_column(SQLEnum(EntityType, native_enum=False), nullable=False, index=True)
    
    # Matching criteria (all optional, more specific = higher priority)
    priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # critical, high, medium, low
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # complaint type, incident type, etc.
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contract: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # SLA targets (in hours)
    acknowledgment_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Time to acknowledge
    response_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Time to first response
    resolution_hours: Mapped[float] = mapped_column(Float, nullable=False)  # Time to resolve
    
    # Warning thresholds (percentage of SLA elapsed)
    warning_threshold_percent: Mapped[int] = mapped_column(Integer, default=75)
    
    # Business hours only?
    business_hours_only: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # What counts as business hours
    business_start_hour: Mapped[int] = mapped_column(Integer, default=9)  # 9 AM
    business_end_hour: Mapped[int] = mapped_column(Integer, default=17)  # 5 PM
    exclude_weekends: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Priority for matching (higher = more specific, evaluated first)
    match_priority: Mapped[int] = mapped_column(Integer, default=0)
    
    def __repr__(self) -> str:
        return f"<SLAConfiguration(id={self.id}, entity={self.entity_type}, resolution={self.resolution_hours}h)>"


class SLATracking(Base, TimestampMixin):
    """Track SLA status for individual entities."""
    
    __tablename__ = "sla_tracking"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Entity being tracked
    entity_type: Mapped[EntityType] = mapped_column(SQLEnum(EntityType, native_enum=False), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # SLA configuration used
    sla_config_id: Mapped[int] = mapped_column(ForeignKey("sla_configurations.id"), nullable=False)
    
    # Tracking timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Target times (calculated from SLA config)
    acknowledgment_due: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response_due: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_due: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Status
    acknowledgment_met: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    response_met: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    resolution_met: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    
    # Current SLA status
    warning_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    breach_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Pause tracking (e.g., waiting for customer)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_paused_hours: Mapped[float] = mapped_column(Float, default=0)
    
    def __repr__(self) -> str:
        return f"<SLATracking(id={self.id}, entity={self.entity_type}:{self.entity_id}, breached={self.is_breached})>"


class EscalationLevel(Base, TimestampMixin):
    """Define escalation levels and paths."""
    
    __tablename__ = "escalation_levels"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Entity type this applies to
    entity_type: Mapped[EntityType] = mapped_column(SQLEnum(EntityType, native_enum=False), nullable=False, index=True)
    
    # Level (1 = first escalation, 2 = second, etc.)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Name and description
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Who to escalate to
    escalate_to_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    escalate_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Notification settings
    notification_template: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notify_original_assignee: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_reporter: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Time after previous level (or creation for level 1)
    hours_after_previous: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    def __repr__(self) -> str:
        return f"<EscalationLevel(id={self.id}, entity={self.entity_type}, level={self.level})>"
