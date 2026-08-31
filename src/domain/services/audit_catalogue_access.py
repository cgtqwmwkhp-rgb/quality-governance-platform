"""AUD-DEV-3: who may list the organisation audit catalogue.

Senior app roles (not workforce_roles lookup) plus anyone who already holds
an audit scheduler/reader token. Field workers stay on assigned-to-me.
"""

from __future__ import annotations

from typing import Protocol

PORTAL_AUDIT_SENIOR_ROLES = frozenset({"admin", "manager", "supervisor", "superadmin"})


class _CatalogueUser(Protocol):
    is_superuser: bool

    def has_permission(self, permission: str) -> bool: ...


def _role_names(user: object) -> set[str]:
    names: set[str] = set()
    for role in getattr(user, "roles", None) or []:
        name = getattr(role, "name", None)
        if isinstance(name, str) and name.strip():
            names.add(name.strip().lower())
    return names


def is_audit_catalogue_caller(user: _CatalogueUser) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    if _role_names(user) & PORTAL_AUDIT_SENIOR_ROLES:
        return True
    return (
        user.has_permission("audit:read") or user.has_permission("audit:create") or user.has_permission("audit:update")
    )
