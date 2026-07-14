"""Asset Registry models for equipment tracking and template tagging."""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, Base, CaseInsensitiveEnum, TimestampMixin

if TYPE_CHECKING:
    from src.domain.models.location import Location


class AssetCategory(str, enum.Enum):
    LIFTING = "lifting"
    POWER = "power"
    TRANSPORT = "transport"
    SPECIALIST = "specialist"
    SAFETY = "safety"
    GENERAL = "general"


class AssetStatus(str, enum.Enum):
    ACTIVE = "active"
    VOR = "vor"  # Vehicle Off Road
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"
    QUARANTINED = "quarantined"


class AssetType(Base, TimestampMixin, AuditTrailMixin):
    """Category > Type taxonomy for equipment (e.g. Lifting > Forklift)."""

    __tablename__ = "asset_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[AssetCategory] = mapped_column(CaseInsensitiveEnum(AssetCategory), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    assets: Mapped[List["Asset"]] = relationship("Asset", back_populates="asset_type")
    template_links: Mapped[List["TemplateAssetType"]] = relationship(
        "TemplateAssetType", back_populates="asset_type", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AssetType(id={self.id}, category={self.category}, name='{self.name}')>"


class Asset(Base, TimestampMixin, AuditTrailMixin):
    """Individual equipment instance."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )
    asset_type_id: Mapped[int] = mapped_column(ForeignKey("asset_types.id"), nullable=False, index=True)

    asset_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    make: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    year_of_manufacture: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Lifting-specific
    safe_working_load: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    swl_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Status
    status: Mapped[AssetStatus] = mapped_column(
        CaseInsensitiveEnum(AssetStatus), default=AssetStatus.ACTIVE, index=True
    )

    # Service dates
    last_service_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_service_due: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_loler_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_loler_due: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Location (legacy free-text — kept for back-compat)
    site: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Structured assignment (Safety AM spine)
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    vehicle_reg: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    photo_evidence_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("evidence_assets.id", ondelete="SET NULL"), nullable=True
    )

    # QR code
    qr_code_data: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Metadata
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    asset_type: Mapped["AssetType"] = relationship("AssetType", back_populates="assets")
    location: Mapped[Optional["Location"]] = relationship("Location")

    def __repr__(self) -> str:
        return f"<Asset(id={self.id}, number='{self.asset_number}', name='{self.name}')>"


class AssetAssignmentEvent(Base):
    """Append-only audit of asset owner / location / vehicle assignment changes."""

    __tablename__ = "asset_assignment_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    from_location_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("locations.id"), nullable=True)
    to_location_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("locations.id"), nullable=True)
    from_vehicle_reg: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    to_vehicle_reg: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    from_owner_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    to_owner_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<AssetAssignmentEvent(id={self.id}, asset_id={self.asset_id})>"


class TemplateAssetType(Base, TimestampMixin):
    """Junction table: which templates apply to which asset types."""

    __tablename__ = "template_asset_types"
    __table_args__ = (UniqueConstraint("template_id", "asset_type_id", name="uq_template_asset_type"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("audit_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_type_id: Mapped[int] = mapped_column(
        ForeignKey("asset_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    asset_type: Mapped["AssetType"] = relationship("AssetType", back_populates="template_links")

    def __repr__(self) -> str:
        return f"<TemplateAssetType(template_id={self.template_id}, asset_type_id={self.asset_type_id})>"
