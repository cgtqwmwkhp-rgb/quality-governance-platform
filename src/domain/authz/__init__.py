"""Authorization vocabulary: what permissions exist, and what may be granted.

``src.domain.models.user.User.has_permission`` does exact set-membership against
the tokens stored on a role. Nothing expands, globs or infers. This package is
the written-down vocabulary that makes that check meaningful, plus the write-time
rules that keep ``roles.permissions`` inside it.

Deliberately separate from :mod:`src.domain.models`: the catalogue is a fact
about the code, not a mapped table, and the ABAC tables in
``src/domain/models/permissions.py`` are dead code that is not on any request
path. Nothing here reads or writes a database.
"""

from src.domain.authz.catalogue import (
    ADMIN_ROLE_PERMISSIONS,
    ENFORCED_PERMISSIONS,
    GRANTABLE_PERMISSIONS,
    REFERENCE_NUMBER_PERMISSIONS,
    RESERVED_PERMISSIONS,
    VIEW_ALL_PERMISSIONS,
    is_enforced,
    is_reserved,
)
from src.domain.authz.validation import (
    PermissionValidationError,
    StoredPermissionsDefect,
    canonicalise_permissions_input,
    describe_stored_permissions,
    detect_encoding,
    parse_permissions_like_runtime,
)

__all__ = [
    "ADMIN_ROLE_PERMISSIONS",
    "ENFORCED_PERMISSIONS",
    "GRANTABLE_PERMISSIONS",
    "REFERENCE_NUMBER_PERMISSIONS",
    "RESERVED_PERMISSIONS",
    "VIEW_ALL_PERMISSIONS",
    "PermissionValidationError",
    "StoredPermissionsDefect",
    "canonicalise_permissions_input",
    "describe_stored_permissions",
    "detect_encoding",
    "is_enforced",
    "is_reserved",
    "parse_permissions_like_runtime",
]
