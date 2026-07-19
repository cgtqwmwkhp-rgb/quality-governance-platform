"""Governance Library Wave W2 — facet bundles + restricted-category RBAC.

Permission model (exact strings; User.has_permission has no wildcards):

  staff:   document:read
  manager: document:read, document:create, document:update
  admin:   + admin:manage + document:restricted:{oh|driver|breach}

Restricted taxonomy → permission (not named UID lists):

  02.08 Occupational Health          → document:restricted:oh
  06.03 Driver Compliance            → document:restricted:driver
  11.03 Breach & Security Incident   → document:restricted:breach
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

# Taxonomy IDs from specs/governance-library/taxonomy.json (default_access=restricted)
RESTRICTED_TAXONOMY_PERMISSIONS: dict[str, str] = {
    "02.08": "document:restricted:oh",
    "06.03": "document:restricted:driver",
    "11.03": "document:restricted:breach",
}

PERM_DOCUMENT_READ = "document:read"
PERM_DOCUMENT_CREATE = "document:create"
PERM_DOCUMENT_UPDATE = "document:update"
PERM_ADMIN_MANAGE = "admin:manage"

FACET_STAFF = "staff"
FACET_MANAGER = "manager"
FACET_ADMIN = "admin"


def facet_permission_bundles() -> dict[str, list[str]]:
    """App facets → Role.permissions JSON lists."""
    restricted = list(RESTRICTED_TAXONOMY_PERMISSIONS.values())
    return {
        FACET_STAFF: [PERM_DOCUMENT_READ],
        FACET_MANAGER: [PERM_DOCUMENT_READ, PERM_DOCUMENT_CREATE, PERM_DOCUMENT_UPDATE],
        FACET_ADMIN: [
            PERM_DOCUMENT_READ,
            PERM_DOCUMENT_CREATE,
            PERM_DOCUMENT_UPDATE,
            PERM_ADMIN_MANAGE,
            *restricted,
        ],
    }


def restricted_permission_for_taxonomy(taxonomy_id: Optional[str]) -> Optional[str]:
    """Return the RBAC permission required for a restricted taxonomy id."""
    if not taxonomy_id:
        return None
    return RESTRICTED_TAXONOMY_PERMISSIONS.get(str(taxonomy_id).strip())


def _user_has(user: Any, permission: str) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    checker = getattr(user, "has_permission", None)
    if callable(checker):
        return bool(checker(permission))
    return False


def user_can_read_library_document(
    document: Any,
    user: Any,
    *,
    taxonomy_id: Optional[str] = None,
) -> bool:
    """Return True when the user may see/read the library document."""
    if getattr(user, "is_superuser", False):
        return True

    access = getattr(document, "access_level", None) or "all_staff"
    if access == "all_staff":
        return True
    if access == "managers":
        return _user_has(user, PERM_DOCUMENT_UPDATE) or _user_has(user, PERM_ADMIN_MANAGE)
    if access == "restricted":
        if _user_has(user, PERM_ADMIN_MANAGE):
            return True
        tax = taxonomy_id
        if tax is None:
            category = getattr(document, "category", None)
            tax = getattr(category, "taxonomy_id", None) if category is not None else None
            if tax is None:
                tax = getattr(document, "taxonomy_id", None)
        required = restricted_permission_for_taxonomy(tax)
        if required is None:
            # Fail closed: restricted without a known taxonomy mapping
            return False
        return _user_has(user, required)
    return False


def serialize_permissions(permissions: Sequence[str]) -> str:
    """Encode a permission list for Role.permissions (JSON string)."""
    import json

    cleaned = [str(p).strip() for p in permissions if str(p).strip()]
    return json.dumps(cleaned)


def parse_permissions(raw: Optional[str | Sequence[str]]) -> list[str]:
    """Decode Role.permissions JSON/CSV into a list."""
    import json

    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    text = str(raw).strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
        if isinstance(decoded, list):
            return [str(item).strip() for item in decoded if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [part.strip() for part in text.split(",") if part.strip()]


def merge_facet_into_permissions(
    existing: Optional[str | Sequence[str]],
    facet: str,
) -> str:
    """Union an app facet bundle into an existing Role.permissions payload."""
    bundles = facet_permission_bundles()
    if facet not in bundles:
        raise ValueError(f"Unknown library facet '{facet}'. Expected one of {sorted(bundles)}")
    merged = sorted(set(parse_permissions(existing)) | set(bundles[facet]))
    return serialize_permissions(merged)


def restricted_taxonomy_ids() -> tuple[str, ...]:
    return tuple(RESTRICTED_TAXONOMY_PERMISSIONS.keys())


def facet_bundle_catalog() -> Mapping[str, list[str]]:
    """Read-only catalog for Admin UI / API docs."""
    return facet_permission_bundles()
