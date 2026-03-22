"""Governance Framework API Routes.

Endpoints for supervisor validation, template approval checks,
competency gating, and scheduling suggestions.
"""

from typing import List

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.governance import (
    GovernanceCompetencyGateResponse,
    GovernanceSchedulingSuggestion,
    GovernanceTemplateCheckResponse,
    GovernanceValidationResponse,
)
from src.api.utils.errors import api_error
from src.api.utils.tenant import apply_tenant_filter
from src.domain.models.engineer import Engineer
from src.domain.services.governance_service import GovernanceService

router = APIRouter()


def _is_workforce_manager(user: CurrentUser) -> bool:
    role_names = {r.name.lower() for r in getattr(user, "roles", []) or []}
    return bool(getattr(user, "is_superuser", False) or "admin" in role_names or "supervisor" in role_names)


async def _assert_governance_engineer_access(db: DbSession, user: CurrentUser, engineer_id: int) -> None:
    if _is_workforce_manager(user):
        return

    query = select(Engineer).where(Engineer.id == engineer_id)
    query = apply_tenant_filter(query, Engineer, user.tenant_id)
    result = await db.execute(query)
    engineer = result.scalar_one_or_none()
    if engineer is None:
        raise HTTPException(status_code=404, detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Engineer not found"))
    if engineer.user_id == user.id:
        return

    raise HTTPException(
        status_code=403,
        detail=api_error(
            ErrorCode.PERMISSION_DENIED,
            "You do not have permission to access this governance data",
        ),
    )


@router.get("/validate-supervisor", response_model=GovernanceValidationResponse)
async def validate_supervisor(
    db: DbSession,
    user: CurrentUser,
    supervisor_id: int = Query(..., description="User id of the supervisor"),
    engineer_id: int = Query(..., description="Engineer id (engineers.id) being assessed"),
):
    """Validate that the supervisor is authorised to assess this engineer."""
    if not _is_workforce_manager(user):
        raise HTTPException(
            status_code=403,
            detail=api_error(
                ErrorCode.PERMISSION_DENIED,
                "You do not have permission to validate supervisor assignments",
            ),
        )
    return await GovernanceService.validate_supervisor(db, supervisor_id, engineer_id, tenant_id=user.tenant_id)


@router.get("/check-template/{template_id}", response_model=GovernanceTemplateCheckResponse)
async def check_template_approval(
    template_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Check if a template is approved for use in assessments/inductions."""
    if not _is_workforce_manager(user):
        raise HTTPException(
            status_code=403,
            detail=api_error(
                ErrorCode.PERMISSION_DENIED,
                "You do not have permission to check workforce templates",
            ),
        )
    return await GovernanceService.check_template_approval(db, template_id, tenant_id=user.tenant_id)


@router.get("/competency-gate", response_model=GovernanceCompetencyGateResponse)
async def check_competency_gate(
    db: DbSession,
    user: CurrentUser,
    engineer_id: int = Query(..., description="Engineer id (engineers.id)"),
    asset_type_id: int = Query(..., description="Asset type id"),
):
    """Check if an engineer has the required competencies to work on an asset type."""
    await _assert_governance_engineer_access(db, user, engineer_id)
    return await GovernanceService.check_competency_gate(db, engineer_id, asset_type_id, tenant_id=user.tenant_id)


@router.get(
    "/scheduling-suggestions/{engineer_id}",
    response_model=List[GovernanceSchedulingSuggestion],
)
async def get_scheduling_suggestions(
    engineer_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Get scheduling suggestions for upcoming assessments (competencies due or expiring)."""
    await _assert_governance_engineer_access(db, user, engineer_id)
    return await GovernanceService.get_scheduling_suggestions(db, engineer_id, tenant_id=user.tenant_id)
