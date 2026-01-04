"""Standards Library API routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.standard import (
    ClauseCreate,
    ClauseResponse,
    ClauseUpdate,
    ControlCreate,
    ControlResponse,
    ControlUpdate,
    StandardCreate,
    StandardDetailResponse,
    StandardListResponse,
    StandardResponse,
    StandardUpdate,
)
from src.domain.models.standard import Clause, Control, Standard

router = APIRouter()


# ============== Standard Endpoints ==============


@router.get("", response_model=StandardListResponse)
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

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Standard.code)

    result = await db.execute(query)
    standards = result.scalars().all()

    return StandardListResponse(
        items=[StandardResponse.model_validate(s) for s in standards],
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=(total or 0 + page_size - 1) // page_size,
    )


@router.post("", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
async def create_standard(
    standard_data: StandardCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> StandardResponse:
    """Create a new standard (superuser only)."""
    # Check if code already exists
    result = await db.execute(select(Standard).where(Standard.code == standard_data.code))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Standard code already exists",
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
            detail="Standard not found",
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
    result = await db.execute(select(Standard).where(Standard.id == standard_id))
    standard = result.scalar_one_or_none()

    if not standard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Standard not found",
        )

    update_data = standard_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(standard, field, value)

    await db.commit()
    await db.refresh(standard)

    return StandardResponse.model_validate(standard)


# ============== Clause Endpoints ==============


@router.get("/{standard_id}/clauses", response_model=list[ClauseResponse])
async def list_clauses(
    standard_id: int,
    db: DbSession,
    current_user: CurrentUser,
    parent_clause_id: Optional[int] = None,
) -> list[ClauseResponse]:
    """List clauses for a standard."""
    # Verify standard exists
    result = await db.execute(select(Standard).where(Standard.id == standard_id))
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Standard not found",
        )

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

    return [ClauseResponse.model_validate(c) for c in clauses]


@router.post("/{standard_id}/clauses", response_model=ClauseResponse, status_code=status.HTTP_201_CREATED)
async def create_clause(
    standard_id: int,
    clause_data: ClauseCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> ClauseResponse:
    """Create a new clause for a standard (superuser only)."""
    # Verify standard exists
    result = await db.execute(select(Standard).where(Standard.id == standard_id))
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Standard not found",
        )

    clause = Clause(
        standard_id=standard_id,
        **clause_data.model_dump(exclude={"standard_id"}),
    )
    db.add(clause)
    await db.commit()

    # Reload with relationships
    result = await db.execute(select(Clause).options(selectinload(Clause.controls)).where(Clause.id == clause.id))
    clause = result.scalar_one()  # type: ignore[assignment]

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
            detail="Clause not found",
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
    result = await db.execute(select(Clause).where(Clause.id == clause_id))
    clause = result.scalar_one_or_none()

    if not clause:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clause not found",
        )

    update_data = clause_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(clause, field, value)

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
    # Verify clause exists
    result = await db.execute(select(Clause).where(Clause.id == clause_id))
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clause not found",
        )

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
    result = await db.execute(select(Control).where(Control.id == control_id))
    control = result.scalar_one_or_none()

    if not control:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Control not found",
        )

    return ControlResponse.model_validate(control)


@router.patch("/controls/{control_id}", response_model=ControlResponse)
async def update_control(
    control_id: int,
    control_data: ControlUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> ControlResponse:
    """Update a control (superuser only)."""
    result = await db.execute(select(Control).where(Control.id == control_id))
    control = result.scalar_one_or_none()

    if not control:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Control not found",
        )

    update_data = control_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(control, field, value)

    await db.commit()
    await db.refresh(control)

    return ControlResponse.model_validate(control)
