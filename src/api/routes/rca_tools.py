"""RCA Tools API Routes.

Provides endpoints for 5-Whys, Fishbone diagrams, and CAPA management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.rca_tools import (
    AddFishboneCauseResponse,
    AddWhyIterationResponse,
    CompleteFishboneResponse,
    CompleteFiveWhysResponse,
    CreateCAPAResponse,
    CreateFishboneResponse,
    CreateFiveWhysResponse,
    EntityFiveWhysListResponse,
    FishboneDetailResponse,
    FiveWhysDetailResponse,
    InvestigationCAPAListResponse,
    OverdueCAPAListResponse,
    SetFishboneRootCauseResponse,
    SetFiveWhysRootCauseResponse,
    UpdateCAPAStatusResponse,
    VerifyCAPAResponse,
)
from src.domain.services.rca_tools import CAPAService, FishboneService, FiveWhysService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter(prefix="/rca-tools", tags=["RCA Tools"])


# =============================================================================
# SCHEMAS
# =============================================================================


class CreateFiveWhysRequest(BaseModel):
    problem_statement: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    investigation_id: Optional[int] = None


class AddWhyRequest(BaseModel):
    why_question: str
    answer: str
    evidence: Optional[str] = None


class SetRootCauseRequest(BaseModel):
    primary_root_cause: str
    contributing_factors: Optional[List[str]] = None


class CompleteAnalysisRequest(BaseModel):
    proposed_actions: Optional[List[Dict[str, Any]]] = None


class CreateFishboneRequest(BaseModel):
    effect_statement: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    investigation_id: Optional[int] = None


class AddCauseRequest(BaseModel):
    category: str = Field(..., description="manpower, method, machine, material, measurement, mother_nature")
    cause: str
    sub_causes: Optional[List[str]] = None


class SetFishboneRootCauseRequest(BaseModel):
    root_cause: str
    root_cause_category: str
    primary_causes: Optional[List[str]] = None


class CreateCAPARequest(BaseModel):
    action_type: str = Field(..., description="corrective or preventive")
    title: str
    description: str
    root_cause_addressed: Optional[str] = None
    five_whys_id: Optional[int] = None
    fishbone_id: Optional[int] = None
    investigation_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    due_date: Optional[datetime] = None
    priority: str = "medium"


class UpdateCAPAStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None


class VerifyCAPARequest(BaseModel):
    verification_notes: Optional[str] = None
    is_effective: bool = True


# =============================================================================
# 5-WHYS ENDPOINTS
# =============================================================================


@router.post("/five-whys", response_model=CreateFiveWhysResponse, status_code=status.HTTP_201_CREATED)
async def create_five_whys_analysis(
    request: CreateFiveWhysRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new 5-Whys analysis."""
    service = FiveWhysService(db)
    analysis = await service.create_analysis(
        problem_statement=request.problem_statement,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        investigation_id=request.investigation_id,
    )
    await invalidate_tenant_cache(current_user.tenant_id, "rca_tools")
    track_metric("rca.mutation", 1)
    track_metric("rca.analysis_started", 1)
    return {
        "id": analysis.id,
        "problem_statement": analysis.problem_statement,
        "whys": analysis.whys,
        "created_at": analysis.created_at,
    }


@router.get("/five-whys/{analysis_id}", response_model=FiveWhysDetailResponse)
async def get_five_whys_analysis(
    analysis_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a 5-Whys analysis by ID."""
    service = FiveWhysService(db)
    analysis = await service.get_analysis(analysis_id)

    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return {
        "id": analysis.id,
        "problem_statement": analysis.problem_statement,
        "whys": analysis.whys,
        "root_causes": analysis.root_causes,
        "primary_root_cause": analysis.primary_root_cause,
        "contributing_factors": analysis.contributing_factors,
        "proposed_actions": analysis.proposed_actions,
        "completed": analysis.completed,
        "completed_at": analysis.completed_at,
        "why_chain": analysis.get_why_chain(),
    }


@router.post("/five-whys/{analysis_id}/add-why", response_model=AddWhyIterationResponse)
async def add_why_iteration(
    analysis_id: int,
    request: AddWhyRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Add a why iteration to an existing analysis."""
    service = FiveWhysService(db)

    try:
        analysis = await service.add_why_iteration(
            analysis_id=analysis_id,
            why_question=request.why_question,
            answer=request.answer,
            evidence=request.evidence,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return {
        "id": analysis.id,
        "whys": analysis.whys,
        "why_count": len(analysis.whys),
    }


@router.post("/five-whys/{analysis_id}/set-root-cause", response_model=SetFiveWhysRootCauseResponse)
async def set_five_whys_root_cause(
    analysis_id: int,
    request: SetRootCauseRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Set the root cause for an analysis."""
    service = FiveWhysService(db)

    try:
        analysis = await service.set_root_cause(
            analysis_id=analysis_id,
            primary_root_cause=request.primary_root_cause,
            contributing_factors=request.contributing_factors,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return {
        "id": analysis.id,
        "primary_root_cause": analysis.primary_root_cause,
        "root_causes": analysis.root_causes,
    }


@router.post("/five-whys/{analysis_id}/complete", response_model=CompleteFiveWhysResponse)
async def complete_five_whys_analysis(
    analysis_id: int,
    request: CompleteAnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Mark a 5-Whys analysis as complete."""
    service = FiveWhysService(db)

    try:
        analysis = await service.complete_analysis(
            analysis_id=analysis_id,
            user_id=current_user.id,
            proposed_actions=request.proposed_actions,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return {
        "id": analysis.id,
        "completed": analysis.completed,
        "completed_at": analysis.completed_at,
    }


@router.get("/five-whys/entity/{entity_type}/{entity_id}", response_model=EntityFiveWhysListResponse)
async def get_five_whys_for_entity(
    entity_type: str,
    entity_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get all 5-Whys analyses for an entity."""
    service = FiveWhysService(db)
    analyses = await service.get_analyses_for_entity(entity_type, entity_id)

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "analyses": [
            {
                "id": a.id,
                "problem_statement": a.problem_statement,
                "completed": a.completed,
                "created_at": a.created_at,
            }
            for a in analyses
        ],
    }


# =============================================================================
# FISHBONE ENDPOINTS
# =============================================================================


@router.post("/fishbone", response_model=CreateFishboneResponse, status_code=status.HTTP_201_CREATED)
async def create_fishbone_diagram(
    request: CreateFishboneRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new Fishbone diagram."""
    service = FishboneService(db)
    diagram = await service.create_diagram(
        effect_statement=request.effect_statement,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        investigation_id=request.investigation_id,
    )
    await invalidate_tenant_cache(current_user.tenant_id, "rca_tools")
    track_metric("rca.mutation", 1)
    return {
        "id": diagram.id,
        "effect_statement": diagram.effect_statement,
        "causes": diagram.causes,
        "created_at": diagram.created_at,
    }


@router.get("/fishbone/{diagram_id}", response_model=FishboneDetailResponse)
async def get_fishbone_diagram(
    diagram_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a Fishbone diagram by ID."""
    service = FishboneService(db)
    diagram = await service.get_diagram(diagram_id)

    if not diagram:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return {
        "id": diagram.id,
        "effect_statement": diagram.effect_statement,
        "causes": diagram.causes,
        "primary_causes": diagram.primary_causes,
        "root_cause": diagram.root_cause,
        "root_cause_category": diagram.root_cause_category,
        "proposed_actions": diagram.proposed_actions,
        "completed": diagram.completed,
        "cause_counts": diagram.count_causes(),
    }


@router.post("/fishbone/{diagram_id}/add-cause", response_model=AddFishboneCauseResponse)
async def add_fishbone_cause(
    diagram_id: int,
    request: AddCauseRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Add a cause to a Fishbone diagram."""
    service = FishboneService(db)

    try:
        diagram = await service.add_cause(
            diagram_id=diagram_id,
            category=request.category,
            cause=request.cause,
            sub_causes=request.sub_causes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)

    return {
        "id": diagram.id,
        "causes": diagram.causes,
        "cause_counts": diagram.count_causes(),
    }


@router.post("/fishbone/{diagram_id}/set-root-cause", response_model=SetFishboneRootCauseResponse)
async def set_fishbone_root_cause(
    diagram_id: int,
    request: SetFishboneRootCauseRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Set the root cause for a Fishbone diagram."""
    service = FishboneService(db)

    try:
        diagram = await service.set_root_cause(
            diagram_id=diagram_id,
            root_cause=request.root_cause,
            root_cause_category=request.root_cause_category,
            primary_causes=request.primary_causes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return {
        "id": diagram.id,
        "root_cause": diagram.root_cause,
        "root_cause_category": diagram.root_cause_category,
    }


@router.post("/fishbone/{diagram_id}/complete", response_model=CompleteFishboneResponse)
async def complete_fishbone_diagram(
    diagram_id: int,
    request: CompleteAnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Mark a Fishbone diagram as complete."""
    service = FishboneService(db)

    try:
        diagram = await service.complete_diagram(
            diagram_id=diagram_id,
            user_id=current_user.id,
            proposed_actions=request.proposed_actions,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return {
        "id": diagram.id,
        "completed": diagram.completed,
        "completed_at": diagram.completed_at,
    }


# =============================================================================
# CAPA ENDPOINTS
# =============================================================================


@router.post("/capa", response_model=CreateCAPAResponse, status_code=status.HTTP_201_CREATED)
async def create_capa(
    request: CreateCAPARequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new CAPA item."""
    service = CAPAService(db)
    capa = await service.create_capa(
        action_type=request.action_type,
        title=request.title,
        description=request.description,
        root_cause_addressed=request.root_cause_addressed,
        five_whys_id=request.five_whys_id,
        fishbone_id=request.fishbone_id,
        investigation_id=request.investigation_id,
        assigned_to_id=request.assigned_to_id,
        due_date=request.due_date,
        priority=request.priority,
    )
    await invalidate_tenant_cache(current_user.tenant_id, "rca_tools")
    track_metric("rca.mutation", 1)
    return {
        "id": capa.id,
        "action_type": capa.action_type,
        "title": capa.title,
        "status": capa.status,
        "due_date": capa.due_date,
    }


@router.patch("/capa/{capa_id}/status", response_model=UpdateCAPAStatusResponse)
async def update_capa_status(
    capa_id: int,
    request: UpdateCAPAStatusRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update CAPA status."""
    service = CAPAService(db)

    try:
        capa = await service.update_status(
            capa_id=capa_id,
            status=request.status,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return {
        "id": capa.id,
        "status": capa.status,
        "completed_at": capa.completed_at,
    }


@router.post("/capa/{capa_id}/verify", response_model=VerifyCAPAResponse)
async def verify_capa(
    capa_id: int,
    request: VerifyCAPARequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Verify a CAPA has been completed effectively."""
    service = CAPAService(db)

    try:
        capa = await service.verify_capa(
            capa_id=capa_id,
            user_id=current_user.id,
            verification_notes=request.verification_notes,
            is_effective=request.is_effective,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return {
        "id": capa.id,
        "status": capa.status,
        "is_effective": capa.is_effective,
        "verified_at": capa.verified_at,
    }


@router.get("/capa/investigation/{investigation_id}", response_model=InvestigationCAPAListResponse)
async def get_capas_for_investigation(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get all CAPAs for an investigation."""
    service = CAPAService(db)
    capas = await service.get_capas_for_investigation(investigation_id)

    return {
        "investigation_id": investigation_id,
        "capas": [
            {
                "id": c.id,
                "action_type": c.action_type,
                "title": c.title,
                "status": c.status,
                "priority": c.priority,
                "due_date": c.due_date,
            }
            for c in capas
        ],
    }


@router.get("/capa/overdue", response_model=OverdueCAPAListResponse)
async def get_overdue_capas(
    db: DbSession,
    current_user: CurrentUser,
):
    """Get all overdue CAPA items."""
    service = CAPAService(db)
    capas = await service.get_overdue_capas()

    return {
        "overdue_count": len(capas),
        "capas": [
            {
                "id": c.id,
                "title": c.title,
                "due_date": c.due_date,
                "status": c.status,
                "priority": c.priority,
            }
            for c in capas
        ],
    }
