"""Risk Register API routes."""

from fastapi import APIRouter

from src.api.dependencies import DbSession, CurrentUser

router = APIRouter()


@router.get("")
async def list_risks(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all risks."""
    return {"message": "Risk Register module - Coming in Phase 2"}


@router.get("/controls")
async def list_risk_controls(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all risk controls."""
    return {"message": "Risk controls - Coming in Phase 2"}
