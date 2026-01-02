"""Audits & Inspections API routes."""

from fastapi import APIRouter

from src.api.dependencies import DbSession, CurrentUser

router = APIRouter()


@router.get("")
async def list_audits(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all audit templates and runs."""
    return {"message": "Audits module - Coming in Phase 2"}


@router.get("/templates")
async def list_audit_templates(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all audit templates."""
    return {"message": "Audit templates - Coming in Phase 2"}


@router.get("/runs")
async def list_audit_runs(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all audit runs."""
    return {"message": "Audit runs - Coming in Phase 2"}
