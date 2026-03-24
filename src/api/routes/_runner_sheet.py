"""Shared helpers for runner-sheet endpoints."""

from fastapi import HTTPException, status


def assert_can_delete_runner_sheet_entry(current_user, author_id: int | None, module_name: str) -> None:
    """Allow deletes for superusers, module delete roles, or the original author."""

    is_superuser = getattr(current_user, "is_superuser", False)
    is_author = author_id is not None and getattr(current_user, "id", None) == author_id
    has_delete_permission = (
        current_user.has_permission(f"{module_name}:delete") if hasattr(current_user, "has_permission") else False
    )

    if is_superuser or is_author or has_delete_permission:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to delete this runner-sheet entry",
    )
