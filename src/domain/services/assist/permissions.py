"""Per-tool RBAC for PlantEx Assist — fail closed."""

from __future__ import annotations

from typing import Optional

from src.domain.services.assist.types import AssistTool, SupportsHasPermission


def tool_is_visible(user: Optional[SupportsHasPermission], tool: AssistTool) -> bool:
    """Whether ``user`` may invoke ``tool``.

    - No user → never (permission-bearing tools must not answer anonymously).
    - Superuser → yes.
    - ``required_permission`` set → ``user.has_permission``.
    - Auth-only tool → yes when a user is present (reason recorded on the tool).
    """
    if user is None:
        return False
    if getattr(user, "is_superuser", False):
        return True
    perm = tool.required_permission
    if perm is None:
        return True
    # Literal ``has_permission`` call — required by the authz extraction scan
    # (DECLARED_DYNAMIC_SITES resolves tokens from ASSIST_TOOLS).
    return bool(user.has_permission(perm))


__all__ = ["tool_is_visible"]
