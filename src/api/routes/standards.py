"""Standards Library API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.standard import Clause, Control, Standard
from src.infrastructure.monitoring.azure_monitor import track_metric

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
    query = select(Standard)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Standard.code.ilike(search_filter))
            | (Standard.name.ilike(search_filter))
            | (Standard.full_name.ilike(search_filter))
        )
    if is_active is not None:
        query = query.where(Standard.is_active == is_active)

    query = query.order_by(Standard.code)
    params = PaginationParams(page=page, page_size=page_size)
    paginated = await paginate(db, query, params)
    track_metric("standards.accessed")

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
    result = await db.execute(select(Standard).where(Standard.code == standard_data.code))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.DUPLICATE_ENTITY,
        )

    standard = Standard(**standard_data.model_dump())
    db.add(standard)
    await db.commit()
    await db.refresh(standard)

    return StandardResponse.model_validate(standard)


@router.get("/{standard_id}", response_model=StandardDetailResponse)
async def get_standard(
    standard_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> StandardDetailResponse:
    """Get a specific standard with its clauses."""
    result = await db.execute(
        select(Standard)
        .options(selectinload(Standard.clauses).selectinload(Clause.controls))
        .where(Standard.id == standard_id)
    )
    standard = result.scalar_one_or_none()

    if not standard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )

    return StandardDetailResponse.model_validate(standard)


@router.patch("/{standard_id}", response_model=StandardResponse)
async def update_standard(
    standard_id: int,
    standard_data: StandardUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> StandardResponse:
    """Update a standard (superuser only)."""
    standard = await get_or_404(db, Standard, standard_id, detail=ErrorCode.ENTITY_NOT_FOUND)
    apply_updates(standard, standard_data, set_updated_at=False)

    await db.commit()
    await db.refresh(standard)

    return StandardResponse.model_validate(standard)


@router.get("/{standard_id}/compliance-score", response_model=ComplianceScoreResponse)
async def get_compliance_score(
    standard_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ComplianceScoreResponse:
    """
    Get compliance score for a standard.

    Calculates compliance based on control implementation status:
    - implemented: 100% weight
    - partial: 50% weight
    - planned/not_implemented/NULL: 0% weight

    Returns setup_required=true if no applicable controls exist.
    """
    standard = await get_or_404(db, Standard, standard_id, detail=ErrorCode.ENTITY_NOT_FOUND)

    control_query = (
        select(Control)
        .join(Clause, Control.clause_id == Clause.id)
        .where(Clause.standard_id == standard_id)
        .where(Control.is_active == True)
        .where(Control.is_applicable == True)
    )
    control_result = await db.execute(control_query)
    controls: list[Control] = list(control_result.scalars().all())

    total_controls = len(controls)

    if total_controls == 0:
        return ComplianceScoreResponse(
            standard_id=standard_id,
            standard_code=standard.code,
            total_controls=0,
            implemented_count=0,
            partial_count=0,
            not_implemented_count=0,
            compliance_percentage=0,
            setup_required=True,
        )

    implemented_count = sum(1 for c in controls if c.implementation_status == "implemented")
    partial_count = sum(1 for c in controls if c.implementation_status == "partial")
    not_implemented_count = total_controls - implemented_count - partial_count

    compliance_percentage = round((implemented_count + 0.5 * partial_count) / total_controls * 100)

    return ComplianceScoreResponse(
        standard_id=standard_id,
        standard_code=standard.code,
        total_controls=total_controls,
        implemented_count=implemented_count,
        partial_count=partial_count,
        not_implemented_count=not_implemented_count,
        compliance_percentage=compliance_percentage,
        setup_required=False,
    )


@router.get("/{standard_id}/controls", response_model=DataListResponse)
async def list_standard_controls(
    standard_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    List all controls for a standard (flat view).

    Returns controls with clause reference, ordered deterministically by:
    clause.sort_order, clause.clause_number, control.control_number, control.id
    """
    await get_or_404(db, Standard, standard_id, detail=ErrorCode.ENTITY_NOT_FOUND)

    query = (
        select(Control, Clause.clause_number, Clause.sort_order)
        .join(Clause, Control.clause_id == Clause.id)
        .where(Clause.standard_id == standard_id)
        .where(Control.is_active == True)
        .order_by(
            Clause.sort_order,
            Clause.clause_number,
            Control.control_number,
            Control.id,
        )
    )
    result = await db.execute(query)
    rows = result.all()

    return {
        "data": [
            ControlListItem(
                id=control.id,
                clause_id=control.clause_id,
                clause_number=clause_number,
                control_number=control.control_number,
                title=control.title,
                implementation_status=control.implementation_status,
                is_applicable=control.is_applicable,
                is_active=control.is_active,
            )
            for control, clause_number, _ in rows
        ]
    }


# ============== Clause Endpoints ==============


@router.get("/{standard_id}/clauses", response_model=DataListResponse)
async def list_clauses(
    standard_id: int,
    db: DbSession,
    current_user: CurrentUser,
    parent_clause_id: Optional[int] = None,
):
    """List clauses for a standard."""
    await get_or_404(db, Standard, standard_id, detail=ErrorCode.ENTITY_NOT_FOUND)

    query = (
        select(Clause)
        .options(selectinload(Clause.controls))
        .where(Clause.standard_id == standard_id)
        .where(Clause.is_active == True)
    )

    if parent_clause_id is not None:
        query = query.where(Clause.parent_clause_id == parent_clause_id)
    else:
        query = query.where(Clause.parent_clause_id.is_(None))

    query = query.order_by(Clause.sort_order, Clause.clause_number)

    result = await db.execute(query)
    clauses = result.scalars().all()

    return {"data": [ClauseResponse.model_validate(c) for c in clauses]}


@router.post("/{standard_id}/clauses", response_model=ClauseResponse, status_code=status.HTTP_201_CREATED)
async def create_clause(
    standard_id: int,
    clause_data: ClauseCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> ClauseResponse:
    """Create a new clause for a standard (superuser only)."""
    await get_or_404(db, Standard, standard_id, detail=ErrorCode.ENTITY_NOT_FOUND)

    clause = Clause(
        standard_id=standard_id,
        **clause_data.model_dump(exclude={"standard_id"}),
    )
    db.add(clause)
    await db.commit()

    result = await db.execute(select(Clause).options(selectinload(Clause.controls)).where(Clause.id == clause.id))
    clause = result.scalar_one()  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-002

    return ClauseResponse.model_validate(clause)


@router.get("/clauses/{clause_id}", response_model=ClauseResponse)
async def get_clause(
    clause_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ClauseResponse:
    """Get a specific clause."""
    result = await db.execute(select(Clause).options(selectinload(Clause.controls)).where(Clause.id == clause_id))
    clause = result.scalar_one_or_none()

    if not clause:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )

    return ClauseResponse.model_validate(clause)


@router.patch("/clauses/{clause_id}", response_model=ClauseResponse)
async def update_clause(
    clause_id: int,
    clause_data: ClauseUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> ClauseResponse:
    """Update a clause (superuser only)."""
    clause = await get_or_404(db, Clause, clause_id, detail=ErrorCode.ENTITY_NOT_FOUND)
    apply_updates(clause, clause_data, set_updated_at=False)

    await db.commit()
    await db.refresh(clause)

    return ClauseResponse.model_validate(clause)


# ============== Control Endpoints ==============


@router.post("/clauses/{clause_id}/controls", response_model=ControlResponse, status_code=status.HTTP_201_CREATED)
async def create_control(
    clause_id: int,
    control_data: ControlCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> ControlResponse:
    """Create a new control for a clause (superuser only)."""
    await get_or_404(db, Clause, clause_id, detail=ErrorCode.ENTITY_NOT_FOUND)

    control = Control(
        clause_id=clause_id,
        **control_data.model_dump(exclude={"clause_id"}),
    )
    db.add(control)
    await db.commit()
    await db.refresh(control)

    return ControlResponse.model_validate(control)


@router.get("/controls/{control_id}", response_model=ControlResponse)
async def get_control(
    control_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ControlResponse:
    """Get a specific control."""
    control = await get_or_404(db, Control, control_id, detail=ErrorCode.ENTITY_NOT_FOUND)
    return ControlResponse.model_validate(control)


@router.patch("/controls/{control_id}", response_model=ControlResponse)
async def update_control(
    control_id: int,
    control_data: ControlUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> ControlResponse:
    """Update a control (superuser only)."""
    control = await get_or_404(db, Control, control_id, detail=ErrorCode.ENTITY_NOT_FOUND)
    apply_updates(control, control_data, set_updated_at=False)

    await db.commit()
    await db.refresh(control)

    return ControlResponse.model_validate(control)
