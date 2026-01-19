"""
Workflow Models - Intelligent Workflow Automation

Supports:
- Workflow templates and definitions
- Approval chains (parallel/sequential)
- Auto-escalation rules
- Conditional routing
- Delegation and substitution
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


class WorkflowStatus(str, Enum):
    """Workflow instance status"""

    DRAFT = "draft"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


class ApprovalType(str, Enum):
    """Type of approval chain"""

    SEQUENTIAL = "sequential"  # One after another
    PARALLEL = "parallel"  # All at once
    ANY = "any"  # Any one approver
    MAJORITY = "majority"  # Majority must approve


class EscalationTrigger(str, Enum):
    """What triggers escalation"""

    TIME_ELAPSED = "time_elapsed"
    SLA_BREACH = "sla_breach"
    NO_RESPONSE = "no_response"
    REJECTION = "rejection"
    MANUAL = "manual"


class WorkflowTemplate(Base):
    """Reusable workflow definition template"""

    __tablename__ = "workflow_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Template info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Trigger configuration
    trigger_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    auto_trigger: Mapped[bool] = mapped_column(Boolean, default=False)

    # SLA configuration
    sla_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    warning_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Steps configuration (JSON array of step definitions)
    steps: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Escalation rules
    escalation_rules: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Notification templates
    notifications: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<WorkflowTemplate(code={self.code}, name={self.name})>"


class WorkflowInstance(Base):
    """Running instance of a workflow"""

    __tablename__ = "workflow_instances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Template reference
    template_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_templates.id"), nullable=False, index=True
    )

    # Entity reference (what this workflow is for)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending")
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    current_step_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Priority
    priority: Mapped[str] = mapped_column(String(20), default="normal")

    # Initiator
    initiated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # SLA tracking
    sla_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sla_warning_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False)

    # Context data
    context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<WorkflowInstance(id={self.id}, status={self.status})>"


class WorkflowStep(Base):
    """Individual step execution record"""

    __tablename__ = "workflow_steps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Instance reference
    instance_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Step info
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Approval info
    approval_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    required_approvers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    actual_approvers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending")

    # Due date
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Outcome
    outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    outcome_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    outcome_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<WorkflowStep(id={self.id}, name={self.step_name})>"


class ApprovalRequest(Base):
    """Individual approval request to a user"""

    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Step reference
    step_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Approver
    approver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )

    # Delegate (if delegated)
    delegated_to: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    delegated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending")

    # Response
    response: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    response_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Due date
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Reminder tracking
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ApprovalRequest(id={self.id}, status={self.status})>"


class EscalationRule(Base):
    """Escalation rule configuration"""

    __tablename__ = "escalation_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Template reference (can be global or template-specific)
    template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("workflow_templates.id"), nullable=True, index=True
    )

    # Rule configuration
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_value: Mapped[int] = mapped_column(Integer, nullable=False)  # hours/count
    trigger_unit: Mapped[str] = mapped_column(String(20), default="hours")

    # Conditions
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Escalation target
    escalate_to_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    escalate_to_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Actions
    actions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Priority change
    change_priority_to: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Notification
    send_notification: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_template: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<EscalationRule(id={self.id}, name={self.name})>"


class EscalationLog(Base):
    """Log of escalation events"""

    __tablename__ = "escalation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # References
    instance_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_instances.id"), nullable=False, index=True
    )
    rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("escalation_rules.id"), nullable=True
    )

    # Escalation details
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)
    from_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    to_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    to_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Previous and new state
    previous_priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    new_priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Notes
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamp
    escalated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<EscalationLog(id={self.id}, trigger={self.trigger})>"


class UserDelegation(Base):
    """Out-of-office delegation configuration"""

    __tablename__ = "user_delegations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # User who is delegating
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Delegate
    delegate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )

    # Time period
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Scope
    delegate_all: Mapped[bool] = mapped_column(Boolean, default=True)
    workflow_types: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True
    )  # If not all

    # Reason
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<UserDelegation(user={self.user_id}, delegate={self.delegate_id})>"
