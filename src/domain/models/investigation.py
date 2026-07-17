"""Investigation domain models.

Investigations replace standalone Root Cause Analysis (RCA) with a template-based
system that can be assigned to Road Traffic Collisions, Reporting Incidents, or Complaints.

Stage 2 Enhancements:
- Source snapshots (immutable record of source at investigation creation)
- Internal comments (threaded, per field/section)
- Revision events (audit trail)
- Optimistic locking (version field)
- Customer pack generation (with redaction rules)
"""

import enum
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, Base, CaseInsensitiveEnum, ReferenceNumberMixin, TimestampMixin


class InvestigationStatus(str, enum.Enum):
    """Investigation status enumeration.

    Workflow: DRAFT -> IN_PROGRESS -> UNDER_REVIEW -> COMPLETED -> CLOSED
    """

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    CLOSED = "closed"


class InvestigationLevel(str, enum.Enum):
    """Investigation level determines required sections (Template Contract v2.1)."""

    MINIMAL = "minimal"  # Event facts, immediate actions, local lessons + sign-off
    LOW = "low"  # Sections 1-3 + Sign-off
    MEDIUM = "medium"  # Sections 1-4 + Sign-off
    HIGH = "high"  # Full HSG245 report, CAPA, fishbone, and management-system review


class CustomerPackAudience(str, enum.Enum):
    """Customer pack audience types."""

    INTERNAL_CUSTOMER = "internal_customer"
    EXTERNAL_CUSTOMER = "external_customer"


class AssignedEntityType(str, enum.Enum):
    """Entity types that can have investigations assigned."""

    ROAD_TRAFFIC_COLLISION = "road_traffic_collision"
    REPORTING_INCIDENT = "reporting_incident"
    COMPLAINT = "complaint"
    NEAR_MISS = "near_miss"


class InvestigationTemplate(Base, TimestampMixin, AuditTrailMixin):
    """Investigation template model.

    Templates define the structure and sections of an investigation,
    including RCA (Root Cause Analysis) as a structured section.
    """

    __tablename__ = "investigation_templates"

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=False, default="1.0")
    is_active = Column(Boolean, nullable=False, default=True)

    # Template structure stored as JSON
    # Example structure:
    # {
    #   "sections": [
    #     {
    #       "id": "rca",
    #       "title": "Root Cause Analysis",
    #       "fields": [
    #         {"id": "problem_statement", "type": "text", "required": true},
    #         {"id": "root_cause", "type": "text", "required": true},
    #         {"id": "contributing_factors", "type": "array", "required": false},
    #         {"id": "corrective_actions", "type": "array", "required": true}
    #       ]
    #     },
    #     {
    #       "id": "evidence",
    #       "title": "Evidence Collection",
    #       "fields": [...]
    #     }
    #   ]
    # }
    structure = Column(JSON, nullable=False)

    # Metadata
    applicable_entity_types = Column(JSON, nullable=False)  # List of AssignedEntityType values

    # Relationships
    investigation_runs = relationship("InvestigationRun", back_populates="template", cascade="all, delete-orphan")
    template_sections: Mapped[List["InvestigationTemplateSection"]] = relationship(
        "InvestigationTemplateSection",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="InvestigationTemplateSection.display_order",
    )
    template_fields: Mapped[List["InvestigationTemplateField"]] = relationship(
        "InvestigationTemplateField",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="InvestigationTemplateField.display_order",
    )

    def __repr__(self) -> str:
        return f"<InvestigationTemplate(id={self.id}, name='{self.name}', version='{self.version}')>"


class InvestigationTemplateSection(Base, TimestampMixin):
    """Normalized section row for an investigation template (W2 hard-spine)."""

    __tablename__ = "investigation_template_sections"
    __table_args__ = (UniqueConstraint("template_id", "section_key", name="uq_inv_template_section_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("investigation_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    template: Mapped["InvestigationTemplate"] = relationship(
        "InvestigationTemplate",
        back_populates="template_sections",
    )
    fields: Mapped[List["InvestigationTemplateField"]] = relationship(
        "InvestigationTemplateField",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="InvestigationTemplateField.display_order",
    )

    def __repr__(self) -> str:
        return (
            f"<InvestigationTemplateSection(id={self.id}, template_id={self.template_id}, "
            f"section_key='{self.section_key}')>"
        )


class InvestigationTemplateField(Base, TimestampMixin):
    """Normalized field row within an investigation template section (W2 hard-spine)."""

    __tablename__ = "investigation_template_fields"
    __table_args__ = (UniqueConstraint("section_id", "field_key", name="uq_inv_template_field_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("investigation_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("investigation_template_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    field_type: Mapped[str] = mapped_column(String(50), nullable=False, default="text")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    template: Mapped["InvestigationTemplate"] = relationship(
        "InvestigationTemplate",
        back_populates="template_fields",
    )
    section: Mapped["InvestigationTemplateSection"] = relationship(
        "InvestigationTemplateSection",
        back_populates="fields",
    )
    run_responses: Mapped[List["InvestigationRunFieldResponse"]] = relationship(
        "InvestigationRunFieldResponse",
        back_populates="template_field",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<InvestigationTemplateField(id={self.id}, section_id={self.section_id}, "
            f"field_key='{self.field_key}')>"
        )


class InvestigationRun(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Investigation run model.

    Represents an actual investigation instance based on a template,
    assigned to a specific entity (RTA, Incident, NearMiss, or Complaint).

    tenant_id is fail-safe NOT NULL when attributable from investigation_templates
    (WCS-TEN2 / C-01 Phase 2).

    Stage 2 Enhancements:
    - Source snapshot: immutable copy of source record at creation
    - Level gating: LOW/MEDIUM/HIGH determines required sections
    - Version: optimistic locking for concurrent edits
    - Approvals and signoffs tracked
    """

    __tablename__ = "investigation_runs"

    id = Column(Integer, primary_key=True, index=True)

    # Multi-tenancy
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Template reference
    template_id = Column(Integer, ForeignKey("investigation_templates.id"), nullable=False, index=True)

    # Assignment to entity
    assigned_entity_type: Mapped[AssignedEntityType] = mapped_column(
        CaseInsensitiveEnum(AssignedEntityType), nullable=False, index=True
    )
    assigned_entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Investigation details
    status: Mapped[InvestigationStatus] = mapped_column(
        CaseInsensitiveEnum(InvestigationStatus),
        nullable=False,
        default=InvestigationStatus.DRAFT,
        index=True,
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Investigation level (determines required sections per Template Contract v2.1)
    level: Mapped[Optional[str]] = mapped_column(CaseInsensitiveEnum(InvestigationLevel), nullable=True, default=None)

    # Investigation data (responses to template fields)
    data = Column(JSON, nullable=False, default=dict)

    # === Stage 2: Source Snapshot (Mapping Contract v1) ===
    # Immutable copy of source record at investigation creation
    source_schema_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Mapping log with reason codes (SOURCE_MISSING_FIELD, TYPE_MISMATCH, etc.)
    mapping_log: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # === Stage 2: Optimistic Locking ===
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # === Stage 2: Approval Workflow ===
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Completion tracking
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Assigned users
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    template = relationship("InvestigationTemplate", back_populates="investigation_runs")
    assigned_to = relationship("User", foreign_keys=[assigned_to_user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_user_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    comments: Mapped[List["InvestigationComment"]] = relationship(
        "InvestigationComment",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
    revision_events: Mapped[List["InvestigationRevisionEvent"]] = relationship(
        "InvestigationRevisionEvent",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
    customer_packs: Mapped[List["InvestigationCustomerPack"]] = relationship(
        "InvestigationCustomerPack",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
    # Actions relationship (fixes "Cannot add action" defect)
    actions: Mapped[List["InvestigationAction"]] = relationship(
        "InvestigationAction",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
    field_responses: Mapped[List["InvestigationRunFieldResponse"]] = relationship(
        "InvestigationRunFieldResponse",
        back_populates="run",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<InvestigationRun(id={self.id}, ref='{self.reference_number}', "
            f"status='{self.status}', entity='{self.assigned_entity_type}:{self.assigned_entity_id}')>"
        )


class InvestigationRunFieldResponse(Base, TimestampMixin):
    """Normalized per-field response for an investigation run (W2 hard-spine)."""

    __tablename__ = "investigation_run_field_responses"
    __table_args__ = (UniqueConstraint("run_id", "template_field_id", name="uq_inv_run_field_response"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("investigation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_field_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("investigation_template_fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_key: Mapped[str] = mapped_column(String(100), nullable=False)
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    value_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    run: Mapped["InvestigationRun"] = relationship("InvestigationRun", back_populates="field_responses")
    template_field: Mapped["InvestigationTemplateField"] = relationship(
        "InvestigationTemplateField",
        back_populates="run_responses",
    )

    def __repr__(self) -> str:
        return f"<InvestigationRunFieldResponse(id={self.id}, run_id={self.run_id}, " f"field_key='{self.field_key}')>"


class InvestigationComment(Base, TimestampMixin):
    """Internal comments on investigations.

    tenant_id is fail-safe NOT NULL when attributable from investigation_runs
    (WCS-TEN2 / C-01 Phase 2).

    Comments are INTERNAL ONLY - never included in customer packs.
    Can be threaded (replies) and attached to specific sections/fields.
    """

    __tablename__ = "investigation_comments"

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("investigation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Comment content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional attachment to specific section/field
    section_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    field_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Threading support
    parent_comment_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("investigation_comments.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Author
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    investigation: Mapped["InvestigationRun"] = relationship("InvestigationRun", back_populates="comments")
    author = relationship("User", foreign_keys=[author_id])
    replies: Mapped[List["InvestigationComment"]] = relationship(
        "InvestigationComment", back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped[Optional["InvestigationComment"]] = relationship(
        "InvestigationComment", back_populates="replies", remote_side=[id]
    )

    def __repr__(self) -> str:
        return f"<InvestigationComment(id={self.id}, investigation_id={self.investigation_id})>"


class InvestigationRevisionEvent(Base, TimestampMixin):
    """Audit trail for investigation changes.

    tenant_id is fail-safe NOT NULL when attributable from investigation_runs
    (WCS-TEN2 / C-01 Phase 2).

    Revision events are INTERNAL ONLY - never included in customer packs.
    """

    __tablename__ = "investigation_revision_events"

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("investigation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Event types: CREATED, DATA_UPDATED, STATUS_CHANGED, COMMENT_ADDED, APPROVED, REJECTED, PACK_GENERATED

    # What changed (for DATA_UPDATED events)
    field_path: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    old_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Version at time of event
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Who made the change
    actor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Additional context (named event_metadata to avoid SQLAlchemy reserved name)
    event_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    investigation: Mapped["InvestigationRun"] = relationship("InvestigationRun", back_populates="revision_events")
    actor = relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:
        return f"<InvestigationRevisionEvent(id={self.id}, event_type='{self.event_type}')>"


class InvestigationCustomerPack(Base, TimestampMixin):
    """Generated customer pack snapshots.

    Immutable artifacts with audience-specific redaction applied.

    tenant_id is fail-safe NOT NULL when attributable from investigation_runs
    (WCS-TEN2 / C-01 Phase 2).
    """

    __tablename__ = "investigation_customer_packs"

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("investigation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Pack identification
    pack_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)

    # Audience (determines redaction rules)
    audience: Mapped[CustomerPackAudience] = mapped_column(CaseInsensitiveEnum(CustomerPackAudience), nullable=False)

    # Pack content (with redaction applied)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Redaction log (what was redacted and why)
    redaction_log: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Evidence assets included (with visibility applied)
    included_assets: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Checksum for integrity verification
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    # Generation metadata
    generated_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    generated_by_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Optional expiry
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    investigation: Mapped["InvestigationRun"] = relationship("InvestigationRun", back_populates="customer_packs")
    generated_by = relationship("User", foreign_keys=[generated_by_id])

    def __repr__(self) -> str:
        return f"<InvestigationCustomerPack(id={self.id}, audience='{self.audience.value}')>"


class InvestigationActionStatus(str, enum.Enum):
    """Status of an investigation action."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_VERIFICATION = "pending_verification"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InvestigationAction(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Action model for corrective/preventive actions from investigations.

    This model fixes the "Cannot add action" defect by providing
    backend persistence for actions within investigations.

    Actions are trackable work items that arise from investigation findings,
    such as corrective actions, preventive measures, or improvements.

    tenant_id is fail-safe NOT NULL when attributable from investigation_runs
    (WCS-TEN2 / C-01 Phase 2).
    """

    __tablename__ = "investigation_actions"

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("investigation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Action details
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), default="corrective")  # corrective, preventive, improvement
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # critical, high, medium, low

    # Assignment
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Status and dates
    # Use native_enum=False to store as VARCHAR instead of PostgreSQL ENUM.
    # This must match migration 20260202_fix_action_status_type which converts the column.
    status: Mapped[InvestigationActionStatus] = mapped_column(
        CaseInsensitiveEnum(InvestigationActionStatus),
        default=InvestigationActionStatus.OPEN,
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Evidence
    completion_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Effectiveness
    effectiveness_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    effectiveness_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_effective: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Relationships
    investigation: Mapped["InvestigationRun"] = relationship("InvestigationRun", back_populates="actions")
    owner = relationship("User", foreign_keys=[owner_id])
    verified_by = relationship("User", foreign_keys=[verified_by_id])

    def __repr__(self) -> str:
        return f"<InvestigationAction(id={self.id}, ref='{self.reference_number}', status='{self.status}')>"
