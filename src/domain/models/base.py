"""Base model mixins for common functionality."""

import enum
from datetime import datetime, timezone
from typing import Optional, Type

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import VARCHAR, TypeDecorator


class CaseInsensitiveEnum(TypeDecorator):
    """VARCHAR-backed enum column that normalises values to lowercase on read.

    Guards against legacy data stored with uppercase labels (e.g. 'DRAFT')
    when the Python enum uses lowercase values (e.g. 'draft').
    """

    impl = VARCHAR
    cache_ok = True

    def __init__(self, enum_class: Type[enum.Enum], length: int = 50):
        self.enum_class = enum_class
        super().__init__(length)

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value.value
        return str(value).lower()

    def process_result_value(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        lowered = value.lower()
        try:
            return self.enum_class(lowered)
        except (ValueError, KeyError):
            for member in self.enum_class:
                if member.value.lower() == lowered or member.name.lower() == lowered:
                    return member
            return value


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class ReferenceNumberMixin:
    """Mixin for auto-generated reference numbers (e.g., AUD-2026-0001)."""

    reference_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted."""
        return self.deleted_at is not None


class AuditTrailMixin:
    """Mixin for audit trail fields."""

    created_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)


# ---------------------------------------------------------------------------
# Data Classification (DPIA / docs/privacy/data-classification.md)
# ---------------------------------------------------------------------------

class DataClassification:
    """Declarative data classification levels for domain models.

    Apply to any SQLAlchemy model to declare its classification tier
    per docs/privacy/data-classification.md (C1–C4).

    Usage on a model class::

        class Incident(Base, TimestampMixin, ...):
            __data_classification__ = DataClassification.C4_RESTRICTED
    """

    C1_PUBLIC = "C1_PUBLIC"
    C2_INTERNAL = "C2_INTERNAL"
    C3_CONFIDENTIAL = "C3_CONFIDENTIAL"
    C4_RESTRICTED = "C4_RESTRICTED"

    HANDLING = {
        "C1_PUBLIC": "No special handling required.",
        "C2_INTERNAL": "Internal use only. No external sharing without approval.",
        "C3_CONFIDENTIAL": "Access limited to authorised users. Encrypted at rest.",
        "C4_RESTRICTED": "PII/special-category. Encrypted, pseudonymised on erasure, audit-logged.",
    }


def get_model_classification(model_class) -> str:
    """Return the data classification level for a model, defaulting to C2."""
    return getattr(model_class, "__data_classification__", DataClassification.C2_INTERNAL)
