"""Governance Framework API Routes.

Endpoints for supervisor validation, template approval checks,
competency gating, and scheduling suggestions.
"""

from typing import List

from fastapi import APIRouter, Query

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.governance import (
    GovernanceCompetencyGateResponse,
    GovernanceSchedulingSuggestion,
    GovernanceTemplateCheckResponse,
    GovernanceValidationResponse,
)
from src.domain.services.governance_service import GovernanceService

router = APIRouter()


@router.get("/validate-supervisor", response_model=GovernanceValidationResponse)
async def validate_supervisor(
    db: DbSession,
    user: CurrentUser,
    supervisor_id: int = Query(..., description="User id of the supervisor"),
    engineer_id: int = Query(..., description="Engineer id (engineers.id) being assessed"),
):
    """Validate that the supervisor is authorised to assess this engineer."""
    return await GovernanceService.validate_supervisor(db, supervisor_id, engineer_id, tenant_id=user.tenant_id)


@router.get("/check-template/{template_id}", response_model=GovernanceTemplateCheckResponse)
async def check_template_approval(
    template_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Check if a template is approved for use in assessments/inductions."""
    return await GovernanceService.check_template_approval(db, template_id, tenant_id=user.tenant_id)


@router.get("/competency-gate", response_model=GovernanceCompetencyGateResponse)
async def check_competency_gate(
    db: DbSession,
    user: CurrentUser,
    engineer_id: int = Query(..., description="Engineer id (engineers.id)"),
    asset_type_id: int = Query(..., description="Asset type id"),
):
    """Check if an engineer has the required competencies to work on an asset type."""
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
    return await GovernanceService.get_scheduling_suggestions(db, engineer_id, tenant_id=user.tenant_id)
