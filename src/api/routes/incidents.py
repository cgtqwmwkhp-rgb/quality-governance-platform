"""Incidents API routes."""

from fastapi import APIRouter

from src.api.dependencies import DbSession, CurrentUser

router = APIRouter()


@router.get("")
async def list_incidents(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all incidents."""
    return {"message": "Incidents module - Coming in Phase 3"}


@router.get("/actions")
async def list_incident_actions(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all incident actions."""
    return {"message": "Incident actions - Coming in Phase 3"}
