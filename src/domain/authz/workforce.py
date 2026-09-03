"""Shared workforce write authorization predicates."""

from __future__ import annotations


def is_workforce_manager(user: object) -> bool:
    """Return whether a principal may perform workforce roster writes."""
    role_names = {str(getattr(role, "name", "")).lower() for role in (getattr(user, "roles", []) or [])}
    return bool(getattr(user, "is_superuser", False) or "admin" in role_names or "supervisor" in role_names)
