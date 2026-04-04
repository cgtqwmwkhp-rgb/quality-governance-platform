"""Engineer API Routes.

REST endpoints for engineer profiles and competency tracking.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Query, status
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
from src.api.schemas.error_codes import ErrorCode
from src.api.utils.errors import api_error
from src.api.utils.tenant import apply_tenant_filter
from src.domain.exceptions import AuthorizationError, BadRequestError, ConflictError, NotFoundError
from src.domain.models.asset import AssetType
from src.domain.models.engineer import CompetencyRecord, Engineer
from src.domain.models.user import User

router = APIRouter()


def _is_workforce_manager(user: CurrentUser) -> bool:
    role_names = {r.name.lower() for r in getattr(user, "roles", []) or []}
    return bool(getattr(user, "is_superuser", False) or "admin" in role_names or "supervisor" in role_names)


def _assert_engineer_access(user: CurrentUser, engineer: Engineer, *, allow_self_read: bool = False) -> None:
    if _is_workforce_manager(user):
        return
    if allow_self_read and engineer.user_id == user.id:
        return
    raise AuthorizationError("You do not have permission to access this engineer record")


def _latest_competency_records(records: list[CompetencyRecord]) -> list[CompetencyRecord]:
    baseline = datetime.min.replace(tzinfo=timezone.utc)

    def sort_key(record: CompetencyRecord) -> tuple[datetime, int]:
        return (
            getattr(record, "assessed_at", None) or getattr(record, "created_at", None) or baseline,
            getattr(record, "id", 0),
        )

    latest_by_asset_type: dict[int, CompetencyRecord] = {}
    for record in records:
        current = latest_by_asset_type.get(record.asset_type_id)
        if current is None or sort_key(record) > sort_key(current):
            latest_by_asset_type[record.asset_type_id] = record

    return sorted(latest_by_asset_type.values(), key=lambda record: record.asset_type_id)


def _effective_competency_state(record: CompetencyRecord) -> str:
    state = record.state.value if hasattr(record.state, "value") else str(record.state)
    expires_at = getattr(record, "expires_at", None)
    if expires_at is not None and expires_at <= datetime.now(timezone.utc) and state in {"active", "due"}:
        return "expired"
    return state


async def _validate_engineer_user_assignment(db: DbSession, user: CurrentUser, target_user_id: int) -> None:
    user_query = select(User).where(User.id == target_user_id, User.is_active.is_(True))
    user_result = await db.execute(user_query)
    target_user = user_result.scalar_one_or_none()
    if target_user is None:
        raise BadRequestError("Assigned user was not found or is inactive")

    if user.tenant_id is not None and target_user.tenant_id != user.tenant_id:
        raise BadRequestError("Assigned user is not in tenant scope")

    existing_query = select(Engineer.id).where(Engineer.user_id == target_user_id)
    existing_query = apply_tenant_filter(existing_query, Engineer, user.tenant_id)
    existing_result = await db.execute(existing_query)
    existing_engineer_id = existing_result.scalar_one_or_none()
    if existing_engineer_id is not None:
        raise ConflictError(
            "An engineer profile already exists for this user",
            details={"engineer_id": existing_engineer_id, "user_id": target_user_id},
        )


@router.get("/", response_model=EngineerListResponse)
async def list_engineers(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    """List engineers with filtering and pagination."""
    query = select(Engineer)
    query = apply_tenant_filter(query, Engineer, user.tenant_id)
    if not _is_workforce_manager(user):
        query = query.where(Engineer.user_id == user.id)
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
    if not _is_workforce_manager(user):
        raise AuthorizationError("You do not have permission to create engineer records")
    await _validate_engineer_user_assignment(db, user, data.user_id)
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
    query = select(Engineer).options(selectinload(Engineer.competency_records)).where(Engineer.id == engineer_id)
    query = apply_tenant_filter(query, Engineer, user.tenant_id)
    result = await db.execute(query)
    engineer = result.scalar_one_or_none()
    if engineer is None:
        raise NotFoundError("Engineer not found")
    _assert_engineer_access(user, engineer, allow_self_read=True)
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
        raise NotFoundError("Engineer not found")
    _assert_engineer_access(user, engineer)

    updates = data.model_dump(exclude_unset=True)
    if "user_id" in updates and updates["user_id"] != engineer.user_id:
        raise BadRequestError("Engineer user assignment cannot be changed via update")
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
    engineer_query = select(Engineer).where(Engineer.id == engineer_id)
    engineer_query = apply_tenant_filter(engineer_query, Engineer, user.tenant_id)
    engineer_result = await db.execute(engineer_query)
    engineer = engineer_result.scalar_one_or_none()
    if engineer is None:
        raise NotFoundError("Engineer not found")
    _assert_engineer_access(user, engineer, allow_self_read=True)

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
    engineer_query = select(Engineer).where(Engineer.id == engineer_id)
    engineer_query = apply_tenant_filter(engineer_query, Engineer, user.tenant_id)
    engineer_result = await db.execute(engineer_query)
    engineer = engineer_result.scalar_one_or_none()
    if engineer is None:
        raise NotFoundError("Engineer not found")
    _assert_engineer_access(user, engineer, allow_self_read=True)

    query = select(CompetencyRecord).where(CompetencyRecord.engineer_id == engineer_id)
    query = apply_tenant_filter(query, CompetencyRecord, user.tenant_id)
    result = await db.execute(query)
    records = result.scalars().all()
    if not records:
        return SkillsMatrixResponse(engineer_id=engineer_id, matrix=[])

    latest_records = _latest_competency_records(records)
    asset_type_ids = list({r.asset_type_id for r in latest_records})
    at_query = select(AssetType).where(AssetType.id.in_(asset_type_ids))
    at_query = apply_tenant_filter(at_query, AssetType, user.tenant_id)
    at_result = await db.execute(at_query)
    asset_types = {at.id: at for at in at_result.scalars().all()}

    matrix = []
    for r in latest_records:
        at = asset_types.get(r.asset_type_id)
        matrix.append(
            SkillsMatrixEntry(
                asset_type_id=r.asset_type_id,
                asset_type_name=at.name if at else None,
                state=_effective_competency_state(r),
                outcome=r.outcome,
                assessed_at=r.assessed_at,
                expires_at=r.expires_at,
            )
        )
    return SkillsMatrixResponse(engineer_id=engineer_id, matrix=matrix)
