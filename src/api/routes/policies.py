"""Policy Library API routes."""

from fastapi import APIRouter

from src.api.dependencies import CurrentUser, DbSession

router = APIRouter()


@router.get("")
async def list_policies(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all policies and documents."""
    return {"message": "Policy Library module - Coming in Phase 4"}


@router.get("/versions")
async def list_policy_versions(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all policy versions."""
    return {"message": "Policy versions - Coming in Phase 4"}
