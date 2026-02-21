"""
Attribute-Based Access Control (ABAC) Service

Provides enterprise-grade permission evaluation with:
- Dynamic policy evaluation
- Field-level access control
- Subject/Resource/Environment attributes
- Permission caching
- Audit logging
"""

import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.permissions import (
    ABACPolicy,
    FieldLevelPermission,
    Permission,
    PermissionAudit,
    Role,
    RolePermission,
    UserRole,
)


class ABACService:
    """
    Attribute-Based Access Control engine.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._policy_cache: dict[str, list[ABACPolicy]] = {}
        self._role_permission_cache: dict[int, set[str]] = {}

    # =========================================================================
    # Main Permission Check
    # =========================================================================

    async def check_permission(
        self,
        subject: dict[str, Any],
        resource_type: str,
        action: str,
        resource: Optional[dict[str, Any]] = None,
        environment: Optional[dict[str, Any]] = None,
        tenant_id: Optional[int] = None,
    ) -> tuple[bool, Optional[ABACPolicy]]:
        """
        Check if a subject can perform an action on a resource.

        Args:
            subject: User attributes (id, roles, department, clearance, etc.)
            resource_type: Type of resource (incident, audit, risk, etc.)
            action: Action to perform (create, read, update, delete, etc.)
            resource: Resource attributes (optional, for resource-based checks)
            environment: Environmental attributes (time, IP, location, etc.)
            tenant_id: Tenant context

        Returns:
            Tuple of (allowed, matched_policy)
        """
        resource = resource or {}
        environment = environment or {}

        # Get applicable policies
        policies = await self._get_applicable_policies(resource_type, action, tenant_id)

        # Sort by priority (highest first) and effect (deny before allow)
        policies.sort(key=lambda p: (-p.priority, 0 if p.effect == "deny" else 1))

        # Evaluate each policy
        for policy in policies:
            if self._evaluate_policy(policy, subject, resource, environment):
                # Log the decision
                self._log_permission_check(
                    tenant_id=tenant_id or 0,
                    user_id=subject.get("id"),
                    resource_type=resource_type,
                    resource_id=resource.get("id"),
                    action=action,
                    decision=policy.effect,
                    policy_id=policy.id,
                    subject=subject,
                    resource=resource,
                    environment=environment,
                )
                return (policy.effect == "allow", policy)

        # Default deny if no policy matches
        self._log_permission_check(
            tenant_id=tenant_id or 0,
            user_id=subject.get("id"),
            resource_type=resource_type,
            resource_id=resource.get("id"),
            action=action,
            decision="deny",
            policy_id=None,
            subject=subject,
            resource=resource,
            environment=environment,
        )
        return (False, None)

    async def check_permission_simple(
        self,
        user_id: int,
        resource_type: str,
        action: str,
        tenant_id: int,
    ) -> bool:
        """Simple permission check using role-based permissions."""
        # Get user's roles
        result = await self.db.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.tenant_id == tenant_id,
                UserRole.is_active == True,
            )
        )
        user_roles = result.scalars().all()

        if not user_roles:
            return False

        # Check if any role has the required permission
        permission_code = f"{resource_type}.{action}"

        for user_role in user_roles:
            role_permissions = await self._get_role_permissions(user_role.role_id)
            if permission_code in role_permissions or f"{resource_type}.*" in role_permissions:
                return True

        return False

    # =========================================================================
    # Field-Level Access
    # =========================================================================

    async def get_allowed_fields(
        self,
        subject: dict[str, Any],
        resource_type: str,
        action: str,
        tenant_id: Optional[int] = None,
    ) -> tuple[set[str], set[str]]:
        """
        Get allowed and denied fields for a resource type.

        Returns:
            Tuple of (allowed_fields, denied_fields)
        """
        allowed = set()
        denied = set()

        # Get field-level permissions
        result = await self.db.execute(
            select(FieldLevelPermission).where(
                FieldLevelPermission.resource_type == resource_type,
                FieldLevelPermission.is_active == True,
                or_(
                    FieldLevelPermission.tenant_id == tenant_id,
                    FieldLevelPermission.tenant_id == None,
                ),
            )
        )
        field_perms = result.scalars().all()

        user_roles = set(subject.get("roles", []))

        for perm in field_perms:
            # Check if this permission applies to the user
            perm_roles = set(perm.role_codes or [])

            if not perm_roles or perm_roles.intersection(user_roles):
                if perm.access_level == "none":
                    denied.add(perm.field_name)
                elif perm.access_level in ["read", "write"]:
                    allowed.add(perm.field_name)
                elif perm.access_level == "mask":
                    # Masked fields are "allowed" but will be transformed
                    allowed.add(perm.field_name)

        return allowed, denied

    async def mask_field_value(
        self,
        resource_type: str,
        field_name: str,
        value: Any,
        tenant_id: Optional[int] = None,
    ) -> Any:
        """Apply masking to a field value based on field-level permissions."""
        result = await self.db.execute(
            select(FieldLevelPermission).where(
                FieldLevelPermission.resource_type == resource_type,
                FieldLevelPermission.field_name == field_name,
                FieldLevelPermission.access_level == "mask",
                FieldLevelPermission.is_active == True,
            )
        )
        perm = result.scalar_one_or_none()

        if not perm:
            return value

        if perm.mask_type == "full":
            return "********"
        elif perm.mask_type == "partial" and perm.mask_pattern:
            return self._apply_mask_pattern(value, perm.mask_pattern)
        elif perm.mask_type == "hash":
            import hashlib

            return hashlib.sha256(str(value).encode()).hexdigest()[:16]
        elif perm.mask_type == "redact":
            return "[REDACTED]"

        return value

    # =========================================================================
    # Policy Management
    # =========================================================================

    async def create_policy(
        self,
        name: str,
        resource_type: str,
        action: str,
        effect: str = "allow",
        subject_conditions: Optional[dict] = None,
        resource_conditions: Optional[dict] = None,
        environment_conditions: Optional[dict] = None,
        tenant_id: Optional[int] = None,
        priority: int = 0,
        **kwargs,
    ) -> ABACPolicy:
        """Create a new ABAC policy."""
        policy = ABACPolicy(
            name=name,
            resource_type=resource_type,
            action=action,
            effect=effect,
            subject_conditions=subject_conditions or {},
            resource_conditions=resource_conditions or {},
            environment_conditions=environment_conditions or {},
            tenant_id=tenant_id,
            priority=priority,
            **kwargs,
        )
        self.db.add(policy)
        await self.db.commit()
        await self.db.refresh(policy)

        # Invalidate cache
        self._invalidate_policy_cache(resource_type, action)

        return policy

    async def get_policies(
        self,
        resource_type: Optional[str] = None,
        tenant_id: Optional[int] = None,
    ) -> list[ABACPolicy]:
        """Get all policies, optionally filtered."""
        stmt = select(ABACPolicy).where(ABACPolicy.is_active == True)

        if resource_type:
            stmt = stmt.where(ABACPolicy.resource_type == resource_type)

        if tenant_id is not None:
            stmt = stmt.where(or_(ABACPolicy.tenant_id == tenant_id, ABACPolicy.tenant_id == None))

        result = await self.db.execute(stmt)
        return result.scalars().all()

    # =========================================================================
    # Role Management
    # =========================================================================

    async def create_role(
        self,
        code: str,
        name: str,
        description: Optional[str] = None,
        tenant_id: Optional[int] = None,
        permission_codes: Optional[list[str]] = None,
        **kwargs,
    ) -> Role:
        """Create a new role with optional permissions."""
        role = Role(
            code=code,
            name=name,
            description=description,
            tenant_id=tenant_id,
            **kwargs,
        )
        self.db.add(role)
        await self.db.flush()

        # Add permissions
        if permission_codes:
            result = await self.db.execute(select(Permission).where(Permission.code.in_(permission_codes)))
            permissions = result.scalars().all()
            for perm in permissions:
                role_perm = RolePermission(role_id=role.id, permission_id=perm.id)
                self.db.add(role_perm)

        await self.db.commit()
        await self.db.refresh(role)

        # Invalidate cache
        if role.id in self._role_permission_cache:
            del self._role_permission_cache[role.id]

        return role

    async def assign_role_to_user(
        self,
        user_id: int,
        role_id: int,
        tenant_id: int,
        scope: Optional[dict] = None,
        valid_until: Optional[datetime] = None,
        granted_by_id: Optional[int] = None,
    ) -> UserRole:
        """Assign a role to a user within a tenant."""
        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            tenant_id=tenant_id,
            scope=scope,
            valid_until=valid_until,
            granted_by_id=granted_by_id,
        )
        self.db.add(user_role)
        await self.db.commit()
        await self.db.refresh(user_role)

        return user_role

    # =========================================================================
    # Internal Methods
    # =========================================================================

    async def _get_applicable_policies(
        self,
        resource_type: str,
        action: str,
        tenant_id: Optional[int],
    ) -> list[ABACPolicy]:
        """Get all policies that could apply to this resource/action."""
        cache_key = f"{tenant_id}:{resource_type}:{action}"

        if cache_key in self._policy_cache:
            return self._policy_cache[cache_key]

        result = await self.db.execute(
            select(ABACPolicy).where(
                ABACPolicy.is_active == True,
                or_(
                    ABACPolicy.resource_type == resource_type,
                    ABACPolicy.resource_type == "*",
                ),
                or_(
                    ABACPolicy.action == action,
                    ABACPolicy.action == "*",
                ),
                or_(
                    ABACPolicy.tenant_id == tenant_id,
                    ABACPolicy.tenant_id == None,
                ),
            )
        )
        policies = result.scalars().all()

        self._policy_cache[cache_key] = policies
        return policies

    def _evaluate_policy(
        self,
        policy: ABACPolicy,
        subject: dict,
        resource: dict,
        environment: dict,
    ) -> bool:
        """Evaluate if a policy matches the current context."""
        # Check subject conditions
        if policy.subject_conditions:
            if not self._evaluate_conditions(policy.subject_conditions, subject):
                return False

        # Check resource conditions
        if policy.resource_conditions:
            if not self._evaluate_conditions(policy.resource_conditions, resource, subject_context=subject):
                return False

        # Check environment conditions
        if policy.environment_conditions:
            if not self._evaluate_conditions(policy.environment_conditions, environment):
                return False

        return True

    def _evaluate_conditions(
        self,
        conditions: dict,
        context: dict,
        subject_context: Optional[dict] = None,
    ) -> bool:
        """
        Evaluate ABAC conditions against a context.

        Supports:
        - Direct value matching: {"role": "admin"}
        - List membership: {"role": ["admin", "manager"]}
        - Operators: {"age": {"gte": 18, "lt": 65}}
        - Variable substitution: {"owner_id": {"eq": "$subject.id"}}
        """
        for key, expected in conditions.items():
            actual = context.get(key)

            if isinstance(expected, dict):
                # Operator-based comparison
                for op, value in expected.items():
                    # Handle variable substitution
                    if isinstance(value, str) and value.startswith("$subject."):
                        if subject_context:
                            value = subject_context.get(value[9:])  # Skip "$subject."

                    if not self._compare(actual, op, value):
                        return False
            elif isinstance(expected, list):
                # Value must be in list
                if actual not in expected:
                    return False
            else:
                # Direct equality
                if actual != expected:
                    return False

        return True

    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        """Perform comparison based on operator."""
        if operator == "eq":
            return actual == expected
        elif operator == "ne":
            return actual != expected
        elif operator == "gt":
            return actual > expected if actual is not None else False
        elif operator == "gte":
            return actual >= expected if actual is not None else False
        elif operator == "lt":
            return actual < expected if actual is not None else False
        elif operator == "lte":
            return actual <= expected if actual is not None else False
        elif operator == "in":
            return actual in expected if expected else False
        elif operator == "nin":
            return actual not in expected if expected else True
        elif operator == "contains":
            return expected in actual if actual else False
        elif operator == "regex":
            return bool(re.match(expected, str(actual))) if actual else False
        elif operator == "exists":
            return (actual is not None) == expected

        return False

    async def _get_role_permissions(self, role_id: int) -> set[str]:
        """Get all permission codes for a role (with caching)."""
        if role_id in self._role_permission_cache:
            return self._role_permission_cache[role_id]

        result = await self.db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        role_perms = result.all()

        codes = {rp[0] for rp in role_perms}
        self._role_permission_cache[role_id] = codes

        return codes

    def _log_permission_check(
        self,
        tenant_id: int,
        user_id: Optional[int],
        resource_type: str,
        resource_id: Optional[str],
        action: str,
        decision: str,
        policy_id: Optional[int],
        subject: dict,
        resource: dict,
        environment: dict,
    ) -> None:
        """Log permission check for audit."""
        audit = PermissionAudit(
            tenant_id=tenant_id,
            user_id=user_id or 0,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            action=action,
            decision=decision,
            matched_policy_id=policy_id,
            subject_attributes=subject,
            resource_attributes=resource,
            environment_attributes=environment,
        )
        self.db.add(audit)

    def _apply_mask_pattern(self, value: Any, pattern: str) -> str:
        """Apply a mask pattern to a value."""
        value_str = str(value)

        # Handle {last4} style patterns
        if "{last4}" in pattern:
            last4 = value_str[-4:] if len(value_str) >= 4 else value_str
            return pattern.replace("{last4}", last4)

        return pattern

    def _invalidate_policy_cache(
        self,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
    ) -> None:
        """Invalidate the policy cache."""
        if resource_type and action:
            keys_to_remove = [k for k in self._policy_cache if resource_type in k and action in k]
            for key in keys_to_remove:
                del self._policy_cache[key]
        else:
            self._policy_cache.clear()
