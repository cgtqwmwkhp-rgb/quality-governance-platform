"""Competency requirement CRUD + allocate — Workforce Northern Star P0 spine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.engineer import (
    CompetencyRequirementAllocateRequest,
    CompetencyRequirementAllocateResponse,
    CompetencyRequirementCreate,
    CompetencyRequirementListResponse,
    CompetencyRequirementResponse,
    CompetencyRequirementUpdate,
)
from src.api.utils.tenant import apply_tenant_filter, require_tenant_id
from src.domain.exceptions import AuthorizationError, NotFoundError
from src.domain.models.engineer import CompetencyRequirement, Engineer, OnboardingChecklist, OnboardingStatus
from src.domain.models.user import User

router = APIRouter()


def _is_workforce_manager(user: CurrentUser) -> bool:
    role_names = {r.name.lower() for r in getattr(user, "roles", []) or []}
    return bool(getattr(user, "is_superuser", False) or "admin" in role_names or "supervisor" in role_names)


def _require_tenant(user: CurrentUser) -> int:
    return require_tenant_id(getattr(user, "tenant_id", None))


def _require_manager(user: CurrentUser) -> None:
    if not _is_workforce_manager(user):
        raise AuthorizationError("You do not have permission to manage competency requirements")


@router.get("/", response_model=CompetencyRequirementListResponse)
async def list_competency_requirements(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    asset_type_id: Optional[int] = None,
    site: Optional[str] = None,
    role_key: Optional[str] = None,
    is_mandatory: Optional[bool] = None,
):
    """List competency requirements for the caller's tenant."""
    tenant_id = _require_tenant(user)
    query = select(CompetencyRequirement)
    query = apply_tenant_filter(query, CompetencyRequirement, tenant_id)
    if asset_type_id is not None:
        query = query.where(CompetencyRequirement.asset_type_id == asset_type_id)
    if site:
        query = query.where(CompetencyRequirement.site.ilike(site))
    if role_key:
        query = query.where(CompetencyRequirement.role_key.ilike(role_key))
    if is_mandatory is not None:
        query = query.where(CompetencyRequirement.is_mandatory.is_(is_mandatory))

    total = (await db.scalar(select(func.count()).select_from(query.subquery()))) or 0
    offset = (page - 1) * page_size
    items = (await db.execute(query.order_by(CompetencyRequirement.id).offset(offset).limit(page_size))).scalars().all()
    pages = (total + page_size - 1) // page_size if total > 0 else 0
    return CompetencyRequirementListResponse(
        items=[CompetencyRequirementResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/", response_model=CompetencyRequirementResponse, status_code=status.HTTP_201_CREATED)
async def create_competency_requirement(
    data: CompetencyRequirementCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("engineer:create"))],
):
    """Create a competency requirement with reassessment frequency."""
    tenant_id = _require_tenant(user)
    _require_manager(user)
    requirement = CompetencyRequirement(
        asset_type_id=data.asset_type_id,
        template_id=data.template_id,
        name=data.name,
        description=data.description,
        is_mandatory=data.is_mandatory,
        reassessment_interval_days=data.reassessment_interval_days,
        role_key=data.role_key,
        site=data.site,
        tenant_id=tenant_id,
    )
    db.add(requirement)
    await db.commit()
    await db.refresh(requirement)
    return CompetencyRequirementResponse.model_validate(requirement)


@router.get("/{requirement_id}", response_model=CompetencyRequirementResponse)
async def get_competency_requirement(
    requirement_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Get a competency requirement by id."""
    tenant_id = _require_tenant(user)
    query = select(CompetencyRequirement).where(CompetencyRequirement.id == requirement_id)
    query = apply_tenant_filter(query, CompetencyRequirement, tenant_id)
    requirement = (await db.execute(query)).scalar_one_or_none()
    if requirement is None:
        raise NotFoundError("Competency requirement not found")
    return CompetencyRequirementResponse.model_validate(requirement)


@router.patch("/{requirement_id}", response_model=CompetencyRequirementResponse)
async def update_competency_requirement(
    requirement_id: int,
    data: CompetencyRequirementUpdate,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Update a competency requirement (including reassessment_interval_days)."""
    tenant_id = _require_tenant(user)
    _require_manager(user)
    query = select(CompetencyRequirement).where(CompetencyRequirement.id == requirement_id)
    query = apply_tenant_filter(query, CompetencyRequirement, tenant_id)
    requirement = (await db.execute(query)).scalar_one_or_none()
    if requirement is None:
        raise NotFoundError("Competency requirement not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(requirement, key, value)
    await db.commit()
    await db.refresh(requirement)
    return CompetencyRequirementResponse.model_validate(requirement)


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competency_requirement(
    requirement_id: int,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Delete a competency requirement."""
    tenant_id = _require_tenant(user)
    _require_manager(user)
    query = select(CompetencyRequirement).where(CompetencyRequirement.id == requirement_id)
    query = apply_tenant_filter(query, CompetencyRequirement, tenant_id)
    requirement = (await db.execute(query)).scalar_one_or_none()
    if requirement is None:
        raise NotFoundError("Competency requirement not found")
    await db.delete(requirement)
    await db.commit()
    return None


@router.post(
    "/{requirement_id}/allocate",
    response_model=CompetencyRequirementAllocateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def allocate_competency_requirement(
    requirement_id: int,
    data: CompetencyRequirementAllocateRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Allocate a requirement to engineers via onboarding checklist rows.

    Matching order:
    1. Explicit ``engineer_ids`` when provided
    2. Else engineers in tenant filtered by requirement.site (optional) and match_role_key
    """
    tenant_id = _require_tenant(user)
    _require_manager(user)

    req_q = select(CompetencyRequirement).where(CompetencyRequirement.id == requirement_id)
    req_q = apply_tenant_filter(req_q, CompetencyRequirement, tenant_id)
    requirement = (await db.execute(req_q)).scalar_one_or_none()
    if requirement is None:
        raise NotFoundError("Competency requirement not found")

    eng_q = select(Engineer).where(Engineer.is_active.is_(True))
    eng_q = apply_tenant_filter(eng_q, Engineer, tenant_id)

    if data.engineer_ids:
        eng_q = eng_q.where(Engineer.id.in_(data.engineer_ids))
    else:
        filters: list[Any] = []
        if data.match_site and requirement.site:
            filters.append(Engineer.site.ilike(requirement.site))
        role_key = data.match_role_key or requirement.role_key
        if role_key:
            # role_key may live on job_title or specialisations_json textually
            pattern = f"%{role_key}%"
            filters.append(or_(Engineer.job_title.ilike(pattern), Engineer.department.ilike(pattern)))
        if filters:
            eng_q = eng_q.where(or_(*filters)) if len(filters) > 1 else eng_q.where(filters[0])

    engineers: List[Engineer] = list((await db.execute(eng_q)).scalars().all())
    matched_ids = [e.id for e in engineers]

    existing_ids: set[int] = set()
    if matched_ids:
        existing_q = select(OnboardingChecklist.engineer_id).where(
            OnboardingChecklist.requirement_id == requirement.id,
            OnboardingChecklist.engineer_id.in_(matched_ids),
        )
        existing_ids = set((await db.execute(existing_q)).scalars().all())

    due_date = None
    if data.due_days is not None:
        due_date = datetime.now(timezone.utc) + timedelta(days=data.due_days)

    created_ids: List[int] = []
    skipped: List[int] = []
    for engineer in engineers:
        if engineer.id in existing_ids:
            skipped.append(engineer.id)
            continue
        checklist = OnboardingChecklist(
            engineer_id=engineer.id,
            requirement_id=requirement.id,
            status=OnboardingStatus.PENDING,
            due_date=due_date,
            tenant_id=tenant_id,
        )
        db.add(checklist)
        await db.flush()
        created_ids.append(checklist.id)

    await db.commit()
    return CompetencyRequirementAllocateResponse(
        requirement_id=requirement.id,
        created_checklist_ids=created_ids,
        skipped_engineer_ids=skipped,
        matched_engineer_ids=matched_ids,
    )
