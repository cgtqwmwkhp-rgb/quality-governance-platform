"""Form configuration models for dynamic form builder."""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, TimestampMixin
from src.infrastructure.database import Base


class FormType(str, enum.Enum):
    """Type of form."""

    INCIDENT = "incident"
    NEAR_MISS = "near_miss"
    COMPLAINT = "complaint"
    RTA = "rta"
    AUDIT = "audit"
    RISK_ASSESSMENT = "risk_assessment"
    CUSTOM = "custom"


class FieldType(str, enum.Enum):
    """Type of form field."""

    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    EMAIL = "email"
    PHONE = "phone"
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    TOGGLE = "toggle"
    FILE = "file"
    IMAGE = "image"
    SIGNATURE = "signature"
    LOCATION = "location"
    BODY_MAP = "body_map"
    RATING = "rating"
    RICH_TEXT = "rich_text"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    DIVIDER = "divider"


class FormTemplate(Base, TimestampMixin, AuditTrailMixin):
    """Form template configuration."""

    __tablename__ = "form_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Template identification
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    form_type: Mapped[str] = mapped_column(String(50), default="custom")

    # Version control
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Appearance
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Settings
    allow_drafts: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_attachments: Mapped[bool] = mapped_column(Boolean, default=True)
    require_signature: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_assign_reference: Mapped[bool] = mapped_column(Boolean, default=True)
    reference_prefix: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Notification settings
    notify_on_submit: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_emails: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated

    # Workflow settings
    workflow_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    steps: Mapped[List["FormStep"]] = relationship(
        "FormStep",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="FormStep.order",
    )

    def __repr__(self) -> str:
        return f"<FormTemplate(id={self.id}, name='{self.name}', type='{self.form_type}')>"


class FormStep(Base, TimestampMixin):
    """Form step/section configuration."""

    __tablename__ = "form_steps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("form_templates.id", ondelete="CASCADE"), nullable=False)

    # Step identification
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)

    # Appearance
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Conditional logic
    show_condition: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # JSON condition

    # Relationships
    template: Mapped["FormTemplate"] = relationship("FormTemplate", back_populates="steps")
    fields: Mapped[List["FormField"]] = relationship(
        "FormField",
        back_populates="step",
        cascade="all, delete-orphan",
        order_by="FormField.order",
    )

    def __repr__(self) -> str:
        return f"<FormStep(id={self.id}, name='{self.name}', order={self.order})>"


class FormField(Base, TimestampMixin):
    """Form field configuration."""

    __tablename__ = "form_fields"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("form_steps.id", ondelete="CASCADE"), nullable=False)

    # Field identification
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # Internal key
    label: Mapped[str] = mapped_column(String(200), nullable=False)  # Display label
    field_type: Mapped[str] = mapped_column(String(50), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0)

    # Help text
    placeholder: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    help_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Validation
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    min_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    min_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pattern: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Regex pattern

    # Default value
    default_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Options (for select, radio, checkbox)
    options: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # JSON array of options

    # Conditional logic
    show_condition: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # JSON condition

    # Appearance
    width: Mapped[str] = mapped_column(String(20), default="full")  # full, half, third

    # Relationships
    step: Mapped["FormStep"] = relationship("FormStep", back_populates="fields")

    def __repr__(self) -> str:
        return f"<FormField(id={self.id}, name='{self.name}', type='{self.field_type}')>"


class Contract(Base, TimestampMixin, AuditTrailMixin):
    """Contract configuration for dropdown options."""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Contract details
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Client info
    client_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    client_contact: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    client_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Display order
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<Contract(id={self.id}, name='{self.name}', code='{self.code}')>"


class SystemSetting(Base, TimestampMixin, AuditTrailMixin):
    """System-wide configuration settings."""

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Setting identification
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    category: Mapped[str] = mapped_column(String(50), default="general")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(20), default="string")  # string, number, boolean, json

    # Access control
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # Visible to non-admins
    is_editable: Mapped[bool] = mapped_column(Boolean, default=True)  # Can be edited via UI

    def __repr__(self) -> str:
        return f"<SystemSetting(key='{self.key}', category='{self.category}')>"


class LookupOption(Base, TimestampMixin):
    """Lookup table for dropdown options (roles, departments, etc.)."""

    __tablename__ = "lookup_options"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Option identification
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # e.g., 'roles', 'departments'
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    # Parent for hierarchical options
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lookup_options.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<LookupOption(category='{self.category}', code='{self.code}')>"
