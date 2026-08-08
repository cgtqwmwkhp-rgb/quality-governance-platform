"""Per-hop RBAC filtering for Entity360 (no 360 oracle)."""

from __future__ import annotations

from typing import Any, Optional

# source_type → permission required to see the hop target.
# When no mapping exists, hop is allowed for any authenticated caller
# (matches endpoints gated by auth alone today).
HOP_READ_PERMISSIONS: dict[str, Optional[str]] = {
    "document": "document:read",
    "risk": "risk:read",
    "incident": "incident:read",
    "near_miss": "near_miss:read",
    "rta": "rta:read",
    "complaint": "complaint:read",
    "audit_finding": "audit:read",
    "capa": None,  # capa:read is reserved (auth-only today)
    "action": "action:read",
    "clause": "document:read",
    "job_step": "job:read",
    "job_type": "job:read",
    # CEL list endpoints are auth-gated only today — no compliance:read token.
    "evidence_link": None,
}


def can_view_hop(user: Any, source_type: str) -> bool:
    """True when ``user`` may see a hop of ``source_type``."""
    if user is None:
        return False
    if getattr(user, "is_superuser", False):
        return True
    perm = HOP_READ_PERMISSIONS.get(source_type.strip().lower())
    if perm is None:
        # Unmapped or intentionally auth-only types
        if source_type.strip().lower() in HOP_READ_PERMISSIONS:
            return True
        # Unknown types: deny (fail closed) so new producers must declare access
        return False
    checker = getattr(user, "has_permission", None)
    if not callable(checker):
        return False
    return bool(checker(perm))


def filter_hops(user: Any, hops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop hops the caller cannot view."""
    return [hop for hop in hops if can_view_hop(user, str(hop.get("source_type") or ""))]


__all__ = [
    "HOP_READ_PERMISSIONS",
    "can_view_hop",
    "filter_hops",
]
