"""
Advanced Document Control System Models

Features:
- Version Control with diff comparison
- Multi-level Approval Workflows
- Automatic Distribution & Notification
- Obsolete Document Management
- Controlled Copy Tracking
- Training Integration
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database import Base


class DocumentType(str, Enum):
    """Document types in the management system"""

    POLICY = "policy"
    PROCEDURE = "procedure"
    WORK_INSTRUCTION = "work_instruction"
    FORM = "form"
    RECORD = "record"
    MANUAL = "manual"
    STANDARD = "standard"
    SPECIFICATION = "specification"
    DRAWING = "drawing"
    TEMPLATE = "template"
    REGISTER = "register"
    PLAN = "plan"
    REPORT = "report"
    EXTERNAL = "external"


class DocumentStatus(str, Enum):
    """Document lifecycle status"""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACTIVE = "active"
    UNDER_REVISION = "under_revision"
    OBSOLETE = "obsolete"
    ARCHIVED = "archived"


class ControlledDocument(Base):
    """Main controlled document entity"""

    __tablename__ = "controlled_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Identification
    document_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Version control
    current_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    major_version: Mapped[int] = mapped_column(Integer, default=1)
    minor_version: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    # Ownership
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Review & Approval
    approver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approver_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Effective dates
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_frequency_months: Mapped[int] = mapped_column(Integer, default=12)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # File details
    file_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Standards & Compliance
    relevant_standards: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    relevant_clauses: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    regulatory_requirements: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Distribution
    distribution_list: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    access_level: Mapped[str] = mapped_column(String(50), default="internal")
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=False)

    # Training
    training_required: Mapped[bool] = mapped_column(Boolean, default=False)
    linked_training_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Retention
    retention_period_years: Mapped[int] = mapped_column(Integer, default=7)
    disposal_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Obsolete handling
    obsolete_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    superseded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("controlled_documents.id"), nullable=True)
    obsolete_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metrics
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    download_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ControlledDocument({self.document_number}: {self.title[:30]})>"


class ControlledDocumentVersion(Base):
    """Version history for controlled documents"""

    __tablename__ = "controlled_document_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("controlled_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Version info
    version_number: Mapped[str] = mapped_column(String(20), nullable=False)
    major_version: Mapped[int] = mapped_column(Integer, nullable=False)
    minor_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Change details
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_type: Mapped[str] = mapped_column(String(50), default="revision")  # new, revision, amendment

    # File snapshot
    file_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_content: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)  # For small files/diffs
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Diff information
    diff_from_previous: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sections_changed: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Status at time
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    # Authors
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentApprovalWorkflow(Base):
    """Multi-level approval workflow definitions"""

    __tablename__ = "document_approval_workflows"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Workflow identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Applicability
    applicable_document_types: Mapped[list] = mapped_column(JSON, nullable=False)
    applicable_categories: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    applicable_departments: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Workflow steps (ordered list of approval levels)
    workflow_steps: Mapped[list] = mapped_column(JSON, nullable=False)
    # Each step: {"level": 1, "role": "reviewer", "approvers": [user_ids], "required_approvals": 1, "deadline_days": 5}

    # Settings
    allow_parallel_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    require_all_approvals: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_escalate_after_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notify_on_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_rejection: Mapped[bool] = mapped_column(Boolean, default=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentApprovalInstance(Base):
    """Active approval workflow instances"""

    __tablename__ = "document_approval_instances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    document_id: Mapped[int] = mapped_column(ForeignKey("controlled_documents.id", ondelete="CASCADE"), nullable=False)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("document_approval_workflows.id"), nullable=False)
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("document_versions.id"), nullable=True)

    # Current state
    current_step: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, approved, rejected, cancelled

    # Initiation
    initiated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    initiated_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Completion
    completed_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    final_decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    final_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Due date
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_overdue: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentApprovalAction(Base):
    """Individual approval/rejection actions"""

    __tablename__ = "document_approval_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    instance_id: Mapped[int] = mapped_column(
        ForeignKey("document_approval_instances.id", ondelete="CASCADE"), nullable=False
    )

    # Step info
    workflow_step: Mapped[int] = mapped_column(Integer, nullable=False)

    # Approver
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    approver_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Decision
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # approved, rejected, returned, delegated
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Delegation
    delegated_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    delegation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    action_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentDistribution(Base):
    """Track document distribution to users/departments"""

    __tablename__ = "document_distributions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    document_id: Mapped[int] = mapped_column(ForeignKey("controlled_documents.id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("document_versions.id"), nullable=True)

    # Recipient
    recipient_type: Mapped[str] = mapped_column(String(50), nullable=False)  # user, department, role, external
    recipient_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Distribution details
    distribution_type: Mapped[str] = mapped_column(String(50), default="controlled")  # controlled, uncontrolled, info
    copy_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # For controlled copies
    is_holder_of_record: Mapped[bool] = mapped_column(Boolean, default=False)

    # Notification
    notified_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notification_method: Mapped[str] = mapped_column(String(50), default="email")

    # Acknowledgment
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledgment_required: Mapped[bool] = mapped_column(Boolean, default=True)

    # Access
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Return/Recall (for controlled copies)
    is_recalled: Mapped[bool] = mapped_column(Boolean, default=False)
    recalled_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    return_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    return_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentTrainingLink(Base):
    """Link documents to training requirements"""

    __tablename__ = "document_training_links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    document_id: Mapped[int] = mapped_column(ForeignKey("controlled_documents.id", ondelete="CASCADE"), nullable=False)

    # Training details
    training_title: Mapped[str] = mapped_column(String(255), nullable=False)
    training_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    training_type: Mapped[str] = mapped_column(String(50), default="awareness")  # awareness, competency, certification

    # Target audience
    target_roles: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    target_departments: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)

    # Completion requirements
    completion_deadline_days: Mapped[int] = mapped_column(Integer, default=30)
    retraining_frequency_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Auto-trigger
    trigger_on_new_version: Mapped[bool] = mapped_column(Boolean, default=True)
    trigger_on_new_distribution: Mapped[bool] = mapped_column(Boolean, default=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentAccessLog(Base):
    """Audit trail for document access"""

    __tablename__ = "document_access_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("controlled_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("document_versions.id"), nullable=True)

    # User
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Action
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # view, download, print, email, edit
    action_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ObsoleteDocumentRecord(Base):
    """Track obsolete documents and their handling"""

    __tablename__ = "obsolete_document_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    document_id: Mapped[int] = mapped_column(ForeignKey("controlled_documents.id", ondelete="CASCADE"), nullable=False)

    # Obsolescence details
    obsolete_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    obsolete_reason: Mapped[str] = mapped_column(Text, nullable=False)
    obsoleted_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    obsoleted_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Supersession
    superseded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("controlled_documents.id"), nullable=True)
    superseded_by_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Handling
    watermark_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    physical_copies_recalled: Mapped[bool] = mapped_column(Boolean, default=False)
    recall_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Retention
    retention_required: Mapped[bool] = mapped_column(Boolean, default=True)
    retention_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    disposal_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    disposal_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    disposal_confirmed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Archive location
    archive_location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
