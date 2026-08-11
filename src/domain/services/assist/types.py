"""Assist tool contract — permission-declared read capabilities.

The closed thing is the set of typed tools, not the set of natural-language
questions. Every tool that returns register facts declares its
``required_permission`` (or an ``auth_only_reason`` when routes today are
auth-gated only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class AssistTool:
    """One read capability PlantEx Assist may invoke for an entitled caller.

    ``name`` matches today's grounded intent id so detection stays stable in
    CORE-01. ``required_permission`` must be an ``ENFORCED_PERMISSIONS`` token,
    or ``None`` with a non-empty ``auth_only_reason`` (recorded debt).
    """

    name: str
    module: str
    description: str
    required_permission: Optional[str]
    auth_only_reason: Optional[str] = None
    row_scope: str = "tenant"


class SupportsHasPermission(Protocol):
    is_superuser: bool

    def has_permission(self, permission: str) -> bool: ...


__all__ = [
    "AssistTool",
    "SupportsHasPermission",
]
