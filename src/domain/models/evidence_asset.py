"""Evidence Asset domain model for shared attachment/evidence management.

This module provides a unified system for managing evidence assets across all
record modules (NearMiss, RTA, Complaint) and Investigations. It supports:
- Multiple asset types (photos, videos, PDFs, maps, diagrams, charts, CCTV refs)
- Retention policies and audit trails
- Customer pack inclusion rules
- RBAC at the asset level
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import AuditTrailMixin, TimestampMixin
from src.infrastructure.database import Base


class EvidenceAssetType(str, enum.Enum):
    """Types of evidence assets supported by the platform."""

    PHOTO = "photo"
    VIDEO = "video"
    PDF = "pdf"
    DOCUMENT = "document"  # Word, Excel, etc.
    MAP_PIN = "map_pin"  # GPS coordinates / map location
    DIAGRAM = "diagram"
    CHART = "chart"
    CCTV_REF = "cctv_ref"  # Reference to CCTV footage (not the file itself)
    DASHCAM_REF = "dashcam_ref"  # Reference to dashcam footage
    AUDIO = "audio"
    SIGNATURE = "signature"  # Digital signature image
    OTHER = "other"


class EvidenceSourceModule(str, enum.Enum):
    """Source modules that can have evidence assets attached."""

    NEAR_MISS = "near_miss"
    ROAD_TRAFFIC_COLLISION = "road_traffic_collision"
    COMPLAINT = "complaint"
    INCIDENT = "incident"
    INVESTIGATION = "investigation"
    AUDIT = "audit"
    ACTION = "action"


class EvidenceVisibility(str, enum.Enum):
    """Visibility/inclusion rules for customer packs."""

    INTERNAL_ONLY = "internal_only"  # Never include in any customer pack
    INTERNAL_CUSTOMER = "internal_customer"  # Include only in internal customer packs
    EXTERNAL_ALLOWED = "external_allowed"  # Can be included in external packs (may be redacted)
    PUBLIC = "public"  # Safe for all audiences


class EvidenceRetentionPolicy(str, enum.Enum):
    """Retention policies for evidence assets."""

    STANDARD = "standard"  # Follow standard retention (7 years for records)
    LEGAL_HOLD = "legal_hold"  # Under legal hold, do not delete
    EXTENDED = "extended"  # Extended retention (10+ years)
    TEMPORARY = "temporary"  # Short-term retention (90 days unless promoted)


class EvidenceAsset(Base, TimestampMixin, AuditTrailMixin):
    """Evidence Asset model for unified attachment management.

    Stores metadata about evidence assets uploaded to the platform.
    Actual file content is stored in blob storage; this table stores
    the storage key and metadata.
    """

    __tablename__ = "evidence_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Storage reference
    storage_key: Mapped[str] = mapped_column(
        String(500), nullable=False, unique=True, index=True
    )  # Blob storage key / URL
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)  # MIME type
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # For integrity verification

    # Asset classification
    asset_type: Mapped[EvidenceAssetType] = mapped_column(
        SQLEnum(EvidenceAssetType, native_enum=False),
        nullable=False,
        default=EvidenceAssetType.OTHER,
    )

    # Source linkage (polymorphic association)
    source_module: Mapped[EvidenceSourceModule] = mapped_column(
        SQLEnum(EvidenceSourceModule, native_enum=False),
        nullable=False,
        index=True,
    )
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Optional secondary linkage (e.g., evidence from NearMiss also linked to Investigation)
    linked_investigation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("investigation_runs.id"), nullable=True, index=True
    )

    # Metadata
    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    captured_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # When the evidence was captured (may differ from upload time)
    captured_by_role: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Role of person who captured (driver, technician, etc.)

    # GPS/Location metadata (for photos with EXIF or map pins)
    latitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    location_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Render hints for frontend
    render_hint: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # thumbnail, embed, link, gallery, etc.
    thumbnail_storage_key: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # Key for generated thumbnail

    # Extended metadata (JSON for flexibility)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: { "exif": {...}, "vehicle_reg": "AB12CDE", "impact_point": "front-left" }

    # Visibility and customer pack rules
    visibility: Mapped[EvidenceVisibility] = mapped_column(
        SQLEnum(EvidenceVisibility, native_enum=False),
        nullable=False,
        default=EvidenceVisibility.INTERNAL_CUSTOMER,
    )
    contains_pii: Mapped[bool] = mapped_column(default=False)  # Flag if asset contains PII (faces, plates, etc.)
    redaction_required: Mapped[bool] = mapped_column(
        default=False
    )  # Flag if asset needs redaction before external sharing

    # Retention
    retention_policy: Mapped[EvidenceRetentionPolicy] = mapped_column(
        SQLEnum(EvidenceRetentionPolicy, native_enum=False),
        nullable=False,
        default=EvidenceRetentionPolicy.STANDARD,
    )
    retention_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("ix_evidence_assets_source", "source_module", "source_id"),
        Index("ix_evidence_assets_type", "asset_type"),
        Index("ix_evidence_assets_visibility", "visibility"),
    )

    def __repr__(self) -> str:
        return (
            f"<EvidenceAsset(id={self.id}, type='{self.asset_type.value}', "
            f"source='{self.source_module.value}:{self.source_id}')>"
        )

    @property
    def is_deleted(self) -> bool:
        """Check if asset is soft deleted."""
        return self.deleted_at is not None

    def can_include_in_customer_pack(self, audience: str) -> bool:
        """Check if asset can be included in a customer pack for given audience.

        Args:
            audience: 'internal_customer' or 'external_customer'

        Returns:
            True if asset can be included (may still need redaction)
        """
        if self.visibility == EvidenceVisibility.INTERNAL_ONLY:
            return False
        if audience == "external_customer":
            return self.visibility in (
                EvidenceVisibility.EXTERNAL_ALLOWED,
                EvidenceVisibility.PUBLIC,
            )
        # internal_customer
        return self.visibility in (
            EvidenceVisibility.INTERNAL_CUSTOMER,
            EvidenceVisibility.EXTERNAL_ALLOWED,
            EvidenceVisibility.PUBLIC,
        )
