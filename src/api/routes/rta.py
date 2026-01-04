"""Road Traffic Collision API routes."""

from fastapi import APIRouter

from src.api.dependencies import CurrentUser, DbSession

router = APIRouter()


@router.get("")
async def list_rta(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all road traffic collisions."""
    return {"message": "RTA module - Coming in Phase 3"}


@router.get("/actions")
async def list_rta_actions(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all RTA actions."""
    return {"message": "RTA actions - Coming in Phase 3"}
