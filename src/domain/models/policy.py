"""Policy and Document Library models."""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, ReferenceNumberMixin, TimestampMixin
from src.infrastructure.database import Base


class DocumentType(str, enum.Enum):
    """Type of document."""

    POLICY = "policy"
    PROCEDURE = "procedure"
    WORK_INSTRUCTION = "work_instruction"
    SOP = "sop"
    FORM = "form"
    TEMPLATE = "template"
    GUIDELINE = "guideline"
    MANUAL = "manual"
    RECORD = "record"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    """Status of document."""

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class Policy(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Policy/Document model for the document library."""

    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Document identification
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType, native_enum=False), default=DocumentType.POLICY
    )
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, native_enum=False), default=DocumentStatus.DRAFT
    )

    # Classification
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Comma-separated tags

    # Tenant isolation
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )

    # Ownership
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approver_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Review cycle
    review_frequency_months: Mapped[int] = mapped_column(Integer, default=12)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Standard mapping
    clause_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Access control
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    restricted_to_roles: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Comma-separated role IDs
    restricted_to_departments: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # Relationships
    versions: Mapped[List["PolicyVersion"]] = relationship(
        "PolicyVersion",
        back_populates="policy",
        cascade="all, delete-orphan",
        order_by="PolicyVersion.version_number.desc()",
    )

    @property
    def current_version(self) -> Optional["PolicyVersion"]:
        """Get the current published version."""
        for version in self.versions:
            if version.is_current:
                return version
        return None

    def __repr__(self) -> str:
        return f"<Policy(id={self.id}, ref='{self.reference_number}', title='{self.title[:50]}')>"


class PolicyVersion(Base, TimestampMixin, AuditTrailMixin):
    """Policy version model for version control."""

    __tablename__ = "policy_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )

    # Version info
    version_number: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # e.g., "1.0", "1.1", "2.0"
    version_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Change summary
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    is_major_revision: Mapped[bool] = mapped_column(Boolean, default=False)

    # Content
    content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Rich text content
    file_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # Path to uploaded file
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # In bytes
    file_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # MIME type

    # Approval workflow
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, native_enum=False), default=DocumentStatus.DRAFT
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Effective dates
    effective_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expiry_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Supersession
    supersedes_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("policy_versions.id"),
        nullable=True,
    )

    # Relationships
    policy: Mapped["Policy"] = relationship("Policy", back_populates="versions")

    def __repr__(self) -> str:
        return f"<PolicyVersion(id={self.id}, policy_id={self.policy_id}, version='{self.version_number}')>"
