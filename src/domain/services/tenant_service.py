"""
Multi-Tenancy Service

Provides complete tenant management with:
- Tenant CRUD operations
- User-tenant associations
- Tenant switching
- Custom branding
- Tenant-scoped data access
"""

import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.tenant import Tenant, TenantInvitation, TenantUser


class TenantService:
    """
    Service for multi-tenant operations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Tenant CRUD
    # =========================================================================

    async def create_tenant(
        self,
        name: str,
        slug: str,
        admin_email: str,
        admin_user_id: int,
        subscription_tier: str = "standard",
        **kwargs,
    ) -> Tenant:
        """Create a new tenant with an owner."""
        result = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError(f"Tenant with slug '{slug}' already exists")

        tenant = Tenant(
            name=name,
            slug=slug,
            admin_email=admin_email,
            subscription_tier=subscription_tier,
            **kwargs,
        )
        self.db.add(tenant)
        await self.db.flush()

        tenant_user = TenantUser(
            tenant_id=tenant.id,
            user_id=admin_user_id,
            role="owner",
            is_active=True,
            is_primary=True,
        )
        self.db.add(tenant_user)
        await self.db.commit()
        await self.db.refresh(tenant)

        return tenant

    async def get_tenant(self, tenant_id: int) -> Optional[Tenant]:
        """Get tenant by ID."""
        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    async def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug."""
        result = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()

    async def get_tenant_by_domain(self, domain: str) -> Optional[Tenant]:
        """Get tenant by custom domain."""
        result = await self.db.execute(select(Tenant).where(Tenant.domain == domain))
        return result.scalar_one_or_none()

    async def update_tenant(self, tenant_id: int, **updates) -> Tenant:
        """Update tenant settings."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        for key, value in updates.items():
            if hasattr(tenant, key):
                setattr(tenant, key, value)

        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def update_branding(
        self,
        tenant_id: int,
        logo_url: Optional[str] = None,
        favicon_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        accent_color: Optional[str] = None,
        theme_mode: Optional[str] = None,
        custom_css: Optional[str] = None,
    ) -> Tenant:
        """Update tenant branding."""
        updates = {}
        if logo_url is not None:
            updates["logo_url"] = logo_url
        if favicon_url is not None:
            updates["favicon_url"] = favicon_url
        if primary_color is not None:
            updates["primary_color"] = primary_color
        if secondary_color is not None:
            updates["secondary_color"] = secondary_color
        if accent_color is not None:
            updates["accent_color"] = accent_color
        if theme_mode is not None:
            updates["theme_mode"] = theme_mode
        if custom_css is not None:
            updates["custom_css"] = custom_css

        return await self.update_tenant(tenant_id, **updates)

    # =========================================================================
    # User-Tenant Management
    # =========================================================================

    async def get_user_tenants(self, user_id: int) -> list[TenantUser]:
        """Get all tenants a user belongs to."""
        result = await self.db.execute(
            select(TenantUser).where(
                TenantUser.user_id == user_id, TenantUser.is_active == True
            )
        )
        return result.scalars().all()

    async def get_tenant_users(self, tenant_id: int) -> list[TenantUser]:
        """Get all users in a tenant."""
        result = await self.db.execute(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant_id, TenantUser.is_active == True
            )
        )
        return result.scalars().all()

    async def add_user_to_tenant(
        self,
        tenant_id: int,
        user_id: int,
        role: str = "user",
        is_primary: bool = False,
        custom_permissions: Optional[dict] = None,
    ) -> TenantUser:
        """Add a user to a tenant."""
        result = await self.db.execute(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant_id, TenantUser.user_id == user_id
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.role = role
                await self.db.commit()
                return existing
            raise ValueError("User already belongs to this tenant")

        tenant_user = TenantUser(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            is_primary=is_primary,
            custom_permissions=custom_permissions or {},
        )
        self.db.add(tenant_user)
        await self.db.commit()
        await self.db.refresh(tenant_user)

        return tenant_user

    async def remove_user_from_tenant(self, tenant_id: int, user_id: int) -> bool:
        """Remove a user from a tenant."""
        result = await self.db.execute(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant_id, TenantUser.user_id == user_id
            )
        )
        tenant_user = result.scalar_one_or_none()

        if not tenant_user:
            return False

        if tenant_user.role == "owner":
            result = await self.db.execute(
                select(func.count())
                .select_from(TenantUser)
                .where(
                    TenantUser.tenant_id == tenant_id,
                    TenantUser.role == "owner",
                    TenantUser.is_active == True,
                )
            )
            owner_count = result.scalar_one()
            if owner_count <= 1:
                raise ValueError("Cannot remove the last owner")

        tenant_user.is_active = False
        await self.db.commit()
        return True

    async def update_user_role(
        self, tenant_id: int, user_id: int, new_role: str
    ) -> TenantUser:
        """Update a user's role in a tenant."""
        result = await self.db.execute(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant_id, TenantUser.user_id == user_id
            )
        )
        tenant_user = result.scalar_one_or_none()

        if not tenant_user:
            raise ValueError("User not found in tenant")

        tenant_user.role = new_role
        await self.db.commit()
        await self.db.refresh(tenant_user)

        return tenant_user

    async def set_primary_tenant(self, user_id: int, tenant_id: int) -> TenantUser:
        """Set the primary tenant for a user."""
        result = await self.db.execute(
            select(TenantUser).where(
                TenantUser.user_id == user_id, TenantUser.is_primary == True
            )
        )
        for tu in result.scalars().all():
            tu.is_primary = False

        result = await self.db.execute(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant_id, TenantUser.user_id == user_id
            )
        )
        tenant_user = result.scalar_one_or_none()

        if not tenant_user:
            raise ValueError("User not found in tenant")

        tenant_user.is_primary = True
        await self.db.commit()
        await self.db.refresh(tenant_user)

        return tenant_user

    # =========================================================================
    # Invitations
    # =========================================================================

    async def create_invitation(
        self,
        tenant_id: int,
        email: str,
        invited_by_id: int,
        role: str = "user",
        expires_in_days: int = 7,
    ) -> TenantInvitation:
        """Create an invitation to join a tenant."""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        invitation = TenantInvitation(
            tenant_id=tenant_id,
            email=email,
            role=role,
            token=token,
            invited_by_id=invited_by_id,
            expires_at=expires_at,
        )
        self.db.add(invitation)
        await self.db.commit()
        await self.db.refresh(invitation)

        return invitation

    async def accept_invitation(self, token: str, user_id: int) -> TenantUser:
        """Accept a tenant invitation."""
        result = await self.db.execute(
            select(TenantInvitation).where(
                TenantInvitation.token == token, TenantInvitation.status == "pending"
            )
        )
        invitation = result.scalar_one_or_none()

        if not invitation:
            raise ValueError("Invalid or expired invitation")

        if invitation.expires_at < datetime.utcnow():
            invitation.status = "expired"
            await self.db.commit()
            raise ValueError("Invitation has expired")

        tenant_user = await self.add_user_to_tenant(
            invitation.tenant_id, user_id, invitation.role
        )

        invitation.status = "accepted"
        invitation.accepted_at = datetime.utcnow()
        await self.db.commit()

        return tenant_user

    # =========================================================================
    # Feature Flags
    # =========================================================================

    async def is_feature_enabled(self, tenant_id: int, feature: str) -> bool:
        """Check if a feature is enabled for a tenant."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False

        return tenant.features_enabled.get(feature, False)

    async def enable_feature(self, tenant_id: int, feature: str) -> Tenant:
        """Enable a feature for a tenant."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        features = tenant.features_enabled.copy()
        features[feature] = True
        tenant.features_enabled = features

        await self.db.commit()
        await self.db.refresh(tenant)

        return tenant

    async def disable_feature(self, tenant_id: int, feature: str) -> Tenant:
        """Disable a feature for a tenant."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        features = tenant.features_enabled.copy()
        features[feature] = False
        tenant.features_enabled = features

        await self.db.commit()
        await self.db.refresh(tenant)

        return tenant

    # =========================================================================
    # Subscription & Limits
    # =========================================================================

    async def check_user_limit(self, tenant_id: int) -> tuple[int, int]:
        """Check if tenant has reached user limit. Returns (current, max)."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        result = await self.db.execute(
            select(func.count())
            .select_from(TenantUser)
            .where(TenantUser.tenant_id == tenant_id, TenantUser.is_active == True)
        )
        current_users = result.scalar_one()

        return current_users, tenant.max_users

    async def can_add_user(self, tenant_id: int) -> bool:
        """Check if a new user can be added to the tenant."""
        current, max_users = await self.check_user_limit(tenant_id)
        return current < max_users
