"""Engineer API Routes.

REST endpoints for engineer profiles and competency tracking.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.engineer import (
    CompetencyRecordResponse,
    EngineerCreate,
    EngineerListResponse,
    EngineerResponse,
    EngineerUpdate,
    SkillsMatrixEntry,
    SkillsMatrixResponse,
)
from src.api.utils.tenant import apply_tenant_filter
from src.domain.models.asset import AssetType
from src.domain.models.engineer import CompetencyRecord, Engineer

router = APIRouter()


@router.get("/", response_model=EngineerListResponse)
async def list_engineers(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    """List engineers with filtering and pagination."""
    query = select(Engineer)
    query = apply_tenant_filter(query, Engineer, user.tenant_id)
    if is_active is not None:
        query = query.where(Engineer.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Engineer.employee_number.ilike(pattern),
                Engineer.job_title.ilike(pattern),
                Engineer.department.ilike(pattern),
                Engineer.site.ilike(pattern),
            )
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.scalar(count_q)) or 0
    offset = (page - 1) * page_size
    items_result = await db.execute(query.offset(offset).limit(page_size).order_by(Engineer.id))
    items = items_result.scalars().all()
    pages = (total + page_size - 1) // page_size if total > 0 else 0

    return EngineerListResponse(
        items=[EngineerResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/", response_model=EngineerResponse, status_code=status.HTTP_201_CREATED)
async def create_engineer(
    data: EngineerCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create a new engineer."""
    engineer = Engineer(
        user_id=data.user_id,
        employee_number=data.employee_number,
        job_title=data.job_title,
        department=data.department,
        site=data.site,
        start_date=data.start_date,
        specialisations_json=data.specialisations,
        certifications_json=data.certifications,
        tenant_id=user.tenant_id,
    )
    db.add(engineer)
    await db.commit()
    await db.refresh(engineer)
    return EngineerResponse.model_validate(engineer)


@router.get("/{engineer_id}", response_model=EngineerResponse)
async def get_engineer(
    engineer_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Get an engineer by ID with competency records loaded."""
    query = (
        select(Engineer)
        .options(selectinload(Engineer.competency_records))
        .where(Engineer.id == engineer_id)
    )
    query = apply_tenant_filter(query, Engineer, user.tenant_id)
    result = await db.execute(query)
    engineer = result.scalar_one_or_none()
    if engineer is None:
        raise HTTPException(status_code=404, detail="Engineer not found")
    return EngineerResponse.model_validate(engineer)


@router.patch("/{engineer_id}", response_model=EngineerResponse)
async def update_engineer(
    engineer_id: int,
    data: EngineerUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update an engineer."""
    query = select(Engineer).where(Engineer.id == engineer_id)
    query = apply_tenant_filter(query, Engineer, user.tenant_id)
    result = await db.execute(query)
    engineer = result.scalar_one_or_none()
    if engineer is None:
        raise HTTPException(status_code=404, detail="Engineer not found")

    updates = data.model_dump(exclude_unset=True)
    if "specialisations" in updates:
        updates["specialisations_json"] = updates.pop("specialisations")
    if "certifications" in updates:
        updates["certifications_json"] = updates.pop("certifications")
    for k, v in updates.items():
        setattr(engineer, k, v)
    await db.commit()
    await db.refresh(engineer)
    return EngineerResponse.model_validate(engineer)


@router.get("/{engineer_id}/competencies", response_model=List[CompetencyRecordResponse])
async def list_engineer_competencies(
    engineer_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """List competency records for an engineer."""
    query = select(CompetencyRecord).where(CompetencyRecord.engineer_id == engineer_id)
    query = apply_tenant_filter(query, CompetencyRecord, user.tenant_id)
    result = await db.execute(query)
    records = result.scalars().all()
    return [CompetencyRecordResponse.model_validate(r) for r in records]


@router.get("/{engineer_id}/skills-matrix", response_model=SkillsMatrixResponse)
async def get_skills_matrix(
    engineer_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Get skills matrix: engineer competency across asset types."""
    query = (
        select(CompetencyRecord)
        .where(CompetencyRecord.engineer_id == engineer_id)
    )
    query = apply_tenant_filter(query, CompetencyRecord, user.tenant_id)
    result = await db.execute(query)
    records = result.scalars().all()
    if not records:
        return SkillsMatrixResponse(engineer_id=engineer_id, matrix=[])

    asset_type_ids = list({r.asset_type_id for r in records})
    at_result = await db.execute(select(AssetType).where(AssetType.id.in_(asset_type_ids)))
    asset_types = {at.id: at for at in at_result.scalars().all()}

    matrix = []
    for r in records:
        at = asset_types.get(r.asset_type_id)
        state_val = r.state.value if hasattr(r.state, "value") else str(r.state)
        matrix.append(
            SkillsMatrixEntry(
                asset_type_id=r.asset_type_id,
                asset_type_name=at.name if at else None,
                state=state_val,
                outcome=r.outcome,
                assessed_at=r.assessed_at,
                expires_at=r.expires_at,
            )
        )
    return SkillsMatrixResponse(engineer_id=engineer_id, matrix=matrix)
