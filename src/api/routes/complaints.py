"""Complaints API routes."""

from fastapi import APIRouter

from src.api.dependencies import CurrentUser, DbSession

router = APIRouter()


@router.get("")
async def list_complaints(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all complaints."""
    return {"message": "Complaints module - Coming in Phase 3"}


@router.get("/actions")
async def list_complaint_actions(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all complaint actions."""
    return {"message": "Complaint actions - Coming in Phase 3"}
