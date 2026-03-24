"""Shared helpers for runner-sheet endpoints."""

from fastapi import HTTPException, status

_DELETE_PERMISSION_FALLBACKS: dict[str, tuple[str, ...]] = {
    "near_miss": ("near_miss:update",),
}


def assert_can_delete_runner_sheet_entry(current_user, author_id: int | None, module_name: str) -> None:
    """Allow deletes for superusers, module delete roles, or the original author."""

    is_superuser = getattr(current_user, "is_superuser", False)
    is_author = author_id is not None and getattr(current_user, "id", None) == author_id
    permission_names = (f"{module_name}:delete", *_DELETE_PERMISSION_FALLBACKS.get(module_name, ()))
    has_delete_permission = False
    if hasattr(current_user, "has_permission"):
        has_delete_permission = any(current_user.has_permission(permission_name) for permission_name in permission_names)

    if is_superuser or is_author or has_delete_permission:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to delete this runner-sheet entry",
    )
