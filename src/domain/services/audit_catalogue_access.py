"""AUD-DEV-3: senior role names for organisation-wide run lists.

App roles, not workforce_roles. Field workers still get 200 on GET /runs,
scoped to their own assigned_to_id (scope reduction, not a lockout).
"""

from __future__ import annotations

from typing import Optional, Protocol

PORTAL_AUDIT_SENIOR_ROLES = frozenset({"admin", "manager", "supervisor", "superadmin"})


class _CatalogueUser(Protocol):
    id: int
    is_superuser: bool


def _role_names(user: object) -> set[str]:
    names: set[str] = set()
    for role in getattr(user, "roles", None) or []:
        name = getattr(role, "name", None)
        if isinstance(name, str) and name.strip():
            names.add(name.strip().lower())
    return names


def is_audit_senior(user: _CatalogueUser) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    return bool(_role_names(user) & PORTAL_AUDIT_SENIOR_ROLES)


def effective_assigned_to_filter(user: _CatalogueUser, requested: Optional[int]) -> Optional[int]:
    """Seniors keep the requested assignee (including None = whole tenant).

    Everyone else is forced to their own id, even if they asked for a colleague.
    """
    if is_audit_senior(user):
        return requested
    return int(user.id)
