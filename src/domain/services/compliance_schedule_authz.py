"""Permission helpers for Compliance Schedule (Wave 0 catalogue enforcement).

Wave 1 routes will call these (or ``require_permission`` equivalents). Declaring
literal ``has_permission`` sites here keeps ``test_permission_catalogue`` green
before HTTP surfaces exist, without putting tokens in ``RESERVED_PERMISSIONS``.
"""

from __future__ import annotations

from typing import Protocol


class _PermissionBearer(Protocol):
    def has_permission(self, permission: str) -> bool: ...


def can_read_compliance_schedule(user: _PermissionBearer) -> bool:
    return user.has_permission("compliance_schedule:read")


def can_create_compliance_schedule(user: _PermissionBearer) -> bool:
    return user.has_permission("compliance_schedule:create")


def can_update_compliance_schedule(user: _PermissionBearer) -> bool:
    return user.has_permission("compliance_schedule:update")
