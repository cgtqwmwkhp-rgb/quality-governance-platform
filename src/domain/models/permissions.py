"""
Attribute-Based Access Control (ABAC) Models

Provides enterprise-grade permissions with:
- Attribute-based policies
- Field-level access control
- Dynamic permission evaluation
- Role hierarchies
- Resource-based permissions
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


class Permission(Base):
    """
    Core permission definition.
    
    Permissions are fine-grained access controls that can be combined into roles.
    """
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Permission identity
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Categorization
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # incidents, audits, risks, admin, etc.
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create, read, update, delete, approve, export
    
    # Resource this permission applies to
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)  # incident, audit, risk, user, etc.
    
    # Field-level permissions (optional)
    allowed_fields: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Fields user can access
    restricted_fields: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Fields user cannot access
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)  # System permissions cannot be deleted
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Permission {self.code}>"


class Role(Base):
    """
    Role definition with permission collections (ABAC).
    
    Roles group permissions for easier assignment.
    """
    __tablename__ = "abac_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Multi-tenancy (null = global role)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True)
    
    # Role identity
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Hierarchy
    parent_role_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("abac_roles.id"), nullable=True)
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=0)  # 0 = lowest, higher = more privileged
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)  # System roles cannot be deleted
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)  # Default role for new users
    
    # Metadata
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color for UI
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Icon name
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    role_permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Role {self.code}>"


class RolePermission(Base):
    """
    Association between roles and permissions (ABAC).
    """
    __tablename__ = "abac_role_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("abac_roles.id"), nullable=False)
    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permissions.id"), nullable=False)
    
    # Override conditions (ABAC)
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Additional conditions for this permission
    
    # Relationships
    role = relationship("Role", back_populates="role_permissions")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserRole(Base):
    """
    Assignment of roles to users within a tenant context (ABAC).
    """
    __tablename__ = "abac_user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("abac_roles.id"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    
    # Optional scope restrictions
    scope: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # e.g., {"departments": ["HR", "IT"]}
    
    # Validity period
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Granted by
    granted_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<UserRole user={self.user_id} role={self.role_id}>"


class ABACPolicy(Base):
    """
    Attribute-Based Access Control Policy.
    
    Defines dynamic access rules based on:
    - Subject attributes (user properties)
    - Resource attributes (entity properties)
    - Action being performed
    - Environmental conditions (time, location, etc.)
    """
    __tablename__ = "abac_policies"
    
    __table_args__ = (
        Index("ix_abac_policy_resource", "resource_type", "action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Multi-tenancy (null = global policy)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True)
    
    # Policy identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Target (what this policy applies to)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)  # incident, audit, risk, etc.
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create, read, update, delete, *
    
    # Effect
    effect: Mapped[str] = mapped_column(String(10), default="allow")  # allow, deny
    
    # Priority (higher = evaluated first)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    
    # Subject conditions (who can perform the action)
    subject_conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    # Example: {"role": ["admin", "manager"], "department": ["HR"], "clearance_level": {"gte": 3}}
    
    # Resource conditions (which resources this applies to)
    resource_conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    # Example: {"status": ["open", "in_progress"], "severity": ["low", "medium"], "owner_id": {"eq": "$subject.id"}}
    
    # Environmental conditions (when this applies)
    environment_conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    # Example: {"time_of_day": {"gte": "09:00", "lte": "17:00"}, "ip_range": ["192.168.1.0/24"]}
    
    # Field-level restrictions
    allowed_fields: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    denied_fields: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Obligations (actions to take when policy matches)
    obligations: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {"log": true, "notify": ["admin@company.com"], "mask_fields": ["ssn", "salary"]}
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Metadata
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<ABACPolicy {self.name} {self.effect} {self.resource_type}:{self.action}>"


class FieldLevelPermission(Base):
    """
    Field-level access control for sensitive data.
    
    Controls access to specific fields within an entity based on user attributes.
    """
    __tablename__ = "field_level_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True)
    
    # Target
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Access control
    access_level: Mapped[str] = mapped_column(String(20), default="read")  # none, read, write, mask
    
    # Who has this access
    role_codes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Roles that have this access
    user_attributes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # ABAC conditions
    
    # Masking rules (for sensitive data)
    mask_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # full, partial, hash, redact
    mask_pattern: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "***-**-{last4}"
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<FieldLevelPermission {self.resource_type}.{self.field_name}>"


class PermissionAudit(Base):
    """
    Audit trail for permission checks.
    
    Records every permission evaluation for compliance.
    """
    __tablename__ = "permission_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)
    
    # Request details
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Result
    decision: Mapped[str] = mapped_column(String(10), nullable=False)  # allow, deny
    matched_policy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("abac_policies.id"), nullable=True)
    
    # Context
    subject_attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    resource_attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    environment_attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self) -> str:
        return f"<PermissionAudit {self.decision} {self.resource_type}:{self.action}>"
