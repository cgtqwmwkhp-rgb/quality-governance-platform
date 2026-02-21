"""
Multi-Tenancy Models

Provides complete tenant isolation with:
- Tenant configuration and branding
- User-tenant associations
- Tenant-specific settings
- Custom branding and themes
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


class Tenant(Base):
    """
    Tenant model for multi-tenancy support.

    Each tenant represents a separate organization with isolated data.
    """

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    subscription_tier: Mapped[str] = mapped_column(
        String(50), default="standard"
    )  # free, standard, professional, enterprise

    # Branding
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    favicon_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(7), default="#3B82F6")  # Hex color
    secondary_color: Mapped[str] = mapped_column(String(7), default="#10B981")
    accent_color: Mapped[str] = mapped_column(String(7), default="#8B5CF6")

    # Theme
    theme_mode: Mapped[str] = mapped_column(String(20), default="dark")  # light, dark, system
    custom_css: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Contact
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    support_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Address
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="United Kingdom")

    # Settings
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    features_enabled: Mapped[dict] = mapped_column(JSON, default=dict)  # Feature flags per tenant

    # Limits
    max_users: Mapped[int] = mapped_column(Integer, default=50)
    max_storage_gb: Mapped[int] = mapped_column(Integer, default=10)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    users = relationship("TenantUser", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Tenant {self.name} ({self.slug})>"


class TenantUser(Base):
    """
    Association between users and tenants.

    A user can belong to multiple tenants with different roles.
    """

    __tablename__ = "tenant_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Role within this tenant
    role: Mapped[str] = mapped_column(String(50), default="user")  # owner, admin, manager, user, viewer

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)  # Primary tenant for this user

    # Permissions override (JSON for flexibility)
    custom_permissions: Mapped[dict] = mapped_column(JSON, default=dict)

    # Timestamps
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")

    def __repr__(self) -> str:
        return f"<TenantUser tenant={self.tenant_id} user={self.user_id} role={self.role}>"


class TenantInvitation(Base):
    """
    Invitation to join a tenant.
    """

    __tablename__ = "tenant_invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user")

    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    invited_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, accepted, expired, revoked

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
