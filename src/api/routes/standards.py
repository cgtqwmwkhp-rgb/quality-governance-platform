"""Standards Library API routes — thin controller layer."""

from typing import Optional

from fastapi import APIRouter, Query, status

from src.domain.exceptions import NotFoundError, ValidationError

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.pagination import DataListResponse
from src.api.schemas.standard import (
    ClauseCreate,
    ClauseResponse,
    ClauseUpdate,
    ComplianceScoreResponse,
    ControlCreate,
    ControlListItem,
    ControlResponse,
    ControlUpdate,
    StandardCreate,
    StandardDetailResponse,
    StandardListResponse,
    StandardResponse,
    StandardUpdate,
)
from src.domain.services.standard_service import StandardService

router = APIRouter()


# ============== Standard Endpoints ==============


@router.get("/", response_model=StandardListResponse)
async def list_standards(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = True,
) -> StandardListResponse:
    """List all standards with pagination."""
    service = StandardService(db)
    paginated = await service.list_standards(page=page, page_size=page_size, search=search, is_active=is_active)
    return StandardListResponse(
        items=[StandardResponse.model_validate(s) for s in paginated.items],
        total=paginated.total,
        page=paginated.page,
        page_size=paginated.page_size,
        pages=paginated.pages,
    )


@router.post("/", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
async def create_standard(
    standard_data: StandardCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> StandardResponse:
    """Create a new standard (superuser only)."""
    service = StandardService(db)
    try:
        standard = await service.create_standard(standard_data)
    except ValueError:
        raise ValidationError(ErrorCode.DUPLICATE_ENTITY)
    return StandardResponse.model_validate(standard)


@router.get("/{standard_id}", response_model=StandardDetailResponse)
async def get_standard(
    standard_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> StandardDetailResponse:
    """Get a specific standard with its clauses."""
    service = StandardService(db)
    try:
        standard = await service.get_standard(standard_id)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return StandardDetailResponse.model_validate(standard)


@router.patch("/{standard_id}", response_model=StandardResponse)
async def update_standard(
    standard_id: int,
    standard_data: StandardUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> StandardResponse:
    """Update a standard (superuser only)."""
    service = StandardService(db)
    try:
        standard = await service.update_standard(standard_id, standard_data)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return StandardResponse.model_validate(standard)


@router.get("/{standard_id}/compliance-score", response_model=ComplianceScoreResponse)
async def get_compliance_score(
    standard_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ComplianceScoreResponse:
    """Get compliance score for a standard."""
    service = StandardService(db)
    try:
        score = await service.get_compliance_score(standard_id)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return ComplianceScoreResponse(**score)


@router.get("/{standard_id}/controls", response_model=DataListResponse)
async def list_standard_controls(
    standard_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List all controls for a standard (flat view)."""
    service = StandardService(db)
    try:
        rows = await service.list_standard_controls(standard_id)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return {"data": [ControlListItem(**row) for row in rows]}


# ============== Clause Endpoints ==============


@router.get("/{standard_id}/clauses", response_model=DataListResponse)
async def list_clauses(
    standard_id: int,
    db: DbSession,
    current_user: CurrentUser,
    parent_clause_id: Optional[int] = None,
):
    """List clauses for a standard."""
    service = StandardService(db)
    try:
        clauses = await service.list_clauses(standard_id, parent_clause_id)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return {"data": [ClauseResponse.model_validate(c) for c in clauses]}


@router.post(
    "/{standard_id}/clauses",
    response_model=ClauseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_clause(
    standard_id: int,
    clause_data: ClauseCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> ClauseResponse:
    """Create a new clause for a standard (superuser only)."""
    service = StandardService(db)
    try:
        clause = await service.create_clause(standard_id, clause_data)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return ClauseResponse.model_validate(clause)


@router.get("/clauses/{clause_id}", response_model=ClauseResponse)
async def get_clause(
    clause_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ClauseResponse:
    """Get a specific clause."""
    service = StandardService(db)
    try:
        clause = await service.get_clause(clause_id)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return ClauseResponse.model_validate(clause)


@router.patch("/clauses/{clause_id}", response_model=ClauseResponse)
async def update_clause(
    clause_id: int,
    clause_data: ClauseUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> ClauseResponse:
    """Update a clause (superuser only)."""
    service = StandardService(db)
    try:
        clause = await service.update_clause(clause_id, clause_data)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return ClauseResponse.model_validate(clause)


# ============== Control Endpoints ==============


@router.post(
    "/clauses/{clause_id}/controls",
    response_model=ControlResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_control(
    clause_id: int,
    control_data: ControlCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> ControlResponse:
    """Create a new control for a clause (superuser only)."""
    service = StandardService(db)
    try:
        control = await service.create_control(clause_id, control_data)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return ControlResponse.model_validate(control)


@router.get("/controls/{control_id}", response_model=ControlResponse)
async def get_control(
    control_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ControlResponse:
    """Get a specific control."""
    service = StandardService(db)
    try:
        control = await service.get_control(control_id)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return ControlResponse.model_validate(control)


@router.patch("/controls/{control_id}", response_model=ControlResponse)
async def update_control(
    control_id: int,
    control_data: ControlUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> ControlResponse:
    """Update a control (superuser only)."""
    service = StandardService(db)
    try:
        control = await service.update_control(control_id, control_data)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return ControlResponse.model_validate(control)
