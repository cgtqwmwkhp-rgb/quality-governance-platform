"""Engineer API Routes.

REST endpoints for engineer profiles and competency tracking.

Workforce write dual gate (ACT-053)
------------------------------------
``POST /`` and ``POST /sync-from-pams`` require **both**:

1. RBAC permission ``engineer:create`` on the caller's role facet, **and**
2. Workforce manager facet: ``admin`` or ``supervisor`` role name, or ``is_superuser``.

Granting ``engineer:create`` without a manager facet returns 403 by design — roster
writes stay with HSEQ/supervisor operators, not general staff personas.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.engineer import (
    CompetencyRecordResponse,
    EngineerCreate,
    EngineerLinkStatusResponse,
    EngineerLinkUserRequest,
    EngineerListResponse,
    EngineerResponse,
    EngineerUpdate,
    LinkedUserSummary,
    PamsTechnicianSyncResponse,
    SkillsMatrixEntry,
    SkillsMatrixResponse,
)
from src.api.schemas.error_codes import ErrorCode
from src.api.utils.errors import api_error
from src.api.utils.tenant import apply_tenant_filter, require_tenant_id
from src.domain.exceptions import AuthorizationError, BadRequestError, ConflictError, NotFoundError
from src.domain.models.asset import AssetType
from src.domain.models.engineer import CompetencyRecord, Engineer
from src.domain.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


def _is_workforce_manager(user: CurrentUser) -> bool:
    role_names = {r.name.lower() for r in getattr(user, "roles", []) or []}
    return bool(getattr(user, "is_superuser", False) or "admin" in role_names or "supervisor" in role_names)


def _require_engineer_tenant_id(user: CurrentUser) -> int:
    """All engineer writes/reads require an explicit tenant membership (fail-closed)."""
    return require_tenant_id(getattr(user, "tenant_id", None))


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


async def _validate_engineer_user_assignment(
    db: DbSession,
    user: CurrentUser,
    target_user_id: int,
    *,
    allow_engineer_id: Optional[int] = None,
) -> User:
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
    if existing_engineer_id is not None and existing_engineer_id != allow_engineer_id:
        raise ConflictError(
            "An engineer profile already exists for this user",
            details={"engineer_id": existing_engineer_id, "user_id": target_user_id},
        )
    return target_user


async def _linked_user_summary(db: DbSession, user_id: Optional[int]) -> Optional[LinkedUserSummary]:
    if user_id is None:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    linked = result.scalar_one_or_none()
    # Defensive: mocks / unexpected row shapes must not break engineer list/get.
    if linked is None or not hasattr(linked, "email") or not getattr(linked, "id", None):
        return None
    full_name = (getattr(linked, "full_name", None) or "").strip() or None
    return LinkedUserSummary(id=int(linked.id), email=str(linked.email), full_name=full_name)


async def _engineer_response(db: DbSession, engineer: Engineer) -> EngineerResponse:
    payload = EngineerResponse.model_validate(engineer)
    payload.linked_user = await _linked_user_summary(db, engineer.user_id)
    return payload


@router.get("/", response_model=EngineerListResponse)
async def list_engineers(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    link_status: Optional[Literal["linked", "unlinked"]] = None,
):
    """List engineers with filtering and pagination."""
    tenant_id = _require_engineer_tenant_id(user)
    query = select(Engineer)
    query = apply_tenant_filter(query, Engineer, tenant_id)
    if not _is_workforce_manager(user):
        query = query.where(Engineer.user_id == user.id)
    if is_active is not None:
        query = query.where(Engineer.is_active == is_active)
    if link_status == "linked":
        query = query.where(Engineer.user_id.is_not(None))
    elif link_status == "unlinked":
        query = query.where(Engineer.user_id.is_(None))
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Engineer.employee_number.ilike(pattern),
                Engineer.display_name.ilike(pattern),
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

    coverage_query = select(
        func.count(Engineer.id),
        func.count(Engineer.user_id),
    ).where(Engineer.tenant_id == tenant_id, Engineer.is_active.is_(True))
    if not _is_workforce_manager(user):
        coverage_query = coverage_query.where(Engineer.user_id == user.id)
    active_engineers, linked_active_engineers = (await db.execute(coverage_query)).one()
    active_engineers = int(active_engineers or 0)
    linked_active_engineers = int(linked_active_engineers or 0)

    responses: list[EngineerResponse] = []
    for engineer in items:
        responses.append(await _engineer_response(db, engineer))
    return EngineerListResponse(
        items=responses,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        active_engineers=active_engineers,
        linked_active_engineers=linked_active_engineers,
        linked_coverage_percent=round(linked_active_engineers / active_engineers * 100, 1)
        if active_engineers
        else 0.0,
    )


@router.post("/", response_model=EngineerResponse, status_code=status.HTTP_201_CREATED)
async def create_engineer(
    data: EngineerCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("engineer:create"))],
):
    """Create a new engineer (``engineer:create`` + workforce manager facet)."""
    tenant_id = _require_engineer_tenant_id(user)
    if not _is_workforce_manager(user):
        raise AuthorizationError("You do not have permission to create engineer records")
    if data.user_id is not None:
        await _validate_engineer_user_assignment(db, user, data.user_id)
    engineer = Engineer(
        user_id=data.user_id,
        display_name=data.display_name,
        employee_number=data.employee_number,
        job_title=data.job_title,
        department=data.department,
        site=data.site,
        start_date=data.start_date,
        specialisations_json=data.specialisations,
        certifications_json=data.certifications,
        tenant_id=tenant_id,
    )
    db.add(engineer)
    await db.commit()
    await db.refresh(engineer)
    return await _engineer_response(db, engineer)


@router.get("/by-user/me", response_model=EngineerLinkStatusResponse)
async def get_engineer_by_user_me(
    db: DbSession,
    user: CurrentUser,
):
    """Resolve the authenticated user's linked engineer profile (portal self-inbox).

    Returns HTTP 200 with ``linked: false`` when no Engineer.user_id link exists —
    callers must show an honest "profile not linked" empty state (no fabricated
    passport ticks). Legacy 404 responses may still occur from other layers.
    """
    tenant_id = _require_engineer_tenant_id(user)
    query = select(Engineer).options(selectinload(Engineer.competency_records)).where(Engineer.user_id == user.id)
    query = apply_tenant_filter(query, Engineer, tenant_id)
    result = await db.execute(query)
    engineer = result.scalar_one_or_none()
    if engineer is None:
        logger.info(
            "portal_work_inbox_viewed user_id=%s engineer_linked=false",
            getattr(user, "id", None),
        )
        return EngineerLinkStatusResponse.unlinked()
    _assert_engineer_access(user, engineer, allow_self_read=True)
    logger.info(
        "portal_work_inbox_viewed user_id=%s engineer_id=%s engineer_linked=true",
        getattr(user, "id", None),
        engineer.id,
    )
    return EngineerLinkStatusResponse.from_engineer(engineer)


@router.post("/sync-from-pams", response_model=PamsTechnicianSyncResponse)
async def sync_engineers_from_pams(
    user: Annotated[User, Depends(require_permission("engineer:create"))],
    tenant_id: Optional[int] = Query(None, description="Override tenant; defaults to DEFAULT_TENANT_ID"),
):
    """Sync PAMS technicians into engineer profiles (``engineer:create`` + manager facet)."""
    if not _is_workforce_manager(user):
        raise AuthorizationError("You do not have permission to sync engineers from PAMS")

    from src.domain.exceptions import BadRequestError, ExternalServiceError
    from src.domain.services.pams_technician_sync_service import resolve_tenant_id, sync_pams_technicians
    from src.infrastructure.database import SessionLocal

    # Null-safe tenant: query override → caller membership → DEFAULT_TENANT_ID.
    # Never open SessionLocal writes with an unresolved tenant (FORCE RLS / NOT NULL).
    if tenant_id is not None:
        candidate_tenant_id: Optional[int] = tenant_id
    elif getattr(user, "tenant_id", None) is not None:
        candidate_tenant_id = _require_engineer_tenant_id(user)
    else:
        candidate_tenant_id = None
    effective_tenant_id = resolve_tenant_id(candidate_tenant_id)
    if user.tenant_id is not None and effective_tenant_id != user.tenant_id:
        raise AuthorizationError("You do not have permission to sync engineers for another tenant")

    db = SessionLocal()
    try:
        counts = sync_pams_technicians(db, tenant_id=effective_tenant_id)
    except (BadRequestError, ExternalServiceError, AuthorizationError):
        raise
    except Exception as exc:
        logger.exception(
            "pams_technician_sync unexpected failure tenant_id=%s user_id=%s",
            effective_tenant_id,
            getattr(user, "id", None),
        )
        raise ExternalServiceError(
            "PAMS technician sync failed unexpectedly — check PAMS connectivity and engineer schema",
            details={"cause": type(exc).__name__, "tenant_id": effective_tenant_id},
        ) from exc
    finally:
        db.close()

    logger.info(
        "pams_technician_sync tenant_id=%s created=%s updated=%s deactivated=%s skipped=%s errors=%s user_id=%s",
        effective_tenant_id,
        counts.created,
        counts.updated,
        counts.deactivated,
        counts.skipped,
        counts.errors,
        getattr(user, "id", None),
    )
    return PamsTechnicianSyncResponse(**counts.as_dict())


@router.get("/{engineer_id}", response_model=EngineerResponse)
async def get_engineer(
    engineer_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Get an engineer by ID with competency records loaded."""
    tenant_id = _require_engineer_tenant_id(user)
    query = select(Engineer).options(selectinload(Engineer.competency_records)).where(Engineer.id == engineer_id)
    query = apply_tenant_filter(query, Engineer, tenant_id)
    result = await db.execute(query)
    engineer = result.scalar_one_or_none()
    if engineer is None:
        raise NotFoundError("Engineer not found")
    _assert_engineer_access(user, engineer, allow_self_read=True)
    return await _engineer_response(db, engineer)


@router.patch("/{engineer_id}", response_model=EngineerResponse)
async def update_engineer(
    engineer_id: int,
    data: EngineerUpdate,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Update an engineer on QGP only — never writes back to PAMS."""
    tenant_id = _require_engineer_tenant_id(user)
    query = select(Engineer).where(Engineer.id == engineer_id)
    query = apply_tenant_filter(query, Engineer, tenant_id)
    result = await db.execute(query)
    engineer = result.scalar_one_or_none()
    if engineer is None:
        raise NotFoundError("Engineer not found")
    _assert_engineer_access(user, engineer)

    updates = data.model_dump(exclude_unset=True)
    if "user_id" in updates and updates["user_id"] != engineer.user_id:
        raise BadRequestError("Engineer user assignment cannot be changed via update — use link-user / unlink-user")
    updates.pop("user_id", None)
    if "specialisations" in updates:
        updates["specialisations_json"] = updates.pop("specialisations")
    if "certifications" in updates:
        updates["certifications_json"] = updates.pop("certifications")

    identity_keys = {
        "display_name",
        "employee_number",
        "job_title",
        "department",
        "site",
        "notes",
        "start_date",
        "specialisations_json",
        "certifications_json",
    }
    if identity_keys.intersection(updates) and "qgp_profile_override" not in updates:
        updates["qgp_profile_override"] = True

    for k, v in updates.items():
        setattr(engineer, k, v)
    await db.commit()
    await db.refresh(engineer)
    logger.info(
        "engineer_qgp_profile_updated engineer_id=%s override=%s user_id=%s",
        engineer.id,
        engineer.qgp_profile_override,
        getattr(user, "id", None),
    )
    return await _engineer_response(db, engineer)


@router.post("/{engineer_id}/link-user", response_model=EngineerResponse)
async def link_engineer_user(
    engineer_id: int,
    data: EngineerLinkUserRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Attach a QGP login User to an Engineer person record (does not touch PAMS)."""
    if not _is_workforce_manager(user):
        raise AuthorizationError("You do not have permission to link engineer users")
    tenant_id = _require_engineer_tenant_id(user)
    query = select(Engineer).where(Engineer.id == engineer_id)
    query = apply_tenant_filter(query, Engineer, tenant_id)
    result = await db.execute(query)
    engineer = result.scalar_one_or_none()
    if engineer is None:
        raise NotFoundError("Engineer not found")

    target = await _validate_engineer_user_assignment(db, user, data.user_id, allow_engineer_id=engineer.id)
    engineer.user_id = target.id
    if not (engineer.display_name and engineer.display_name.strip()):
        from src.domain.services.engineer_user_link_service import display_name_for_user

        engineer.display_name = display_name_for_user(target)
    await db.commit()
    await db.refresh(engineer)
    logger.info(
        "engineer_user_linked engineer_id=%s linked_user_id=%s by_user_id=%s",
        engineer.id,
        target.id,
        getattr(user, "id", None),
    )
    return await _engineer_response(db, engineer)


@router.post("/{engineer_id}/unlink-user", response_model=EngineerResponse)
async def unlink_engineer_user(
    engineer_id: int,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Detach QGP login from Engineer — roster person remains (PAMS untouched)."""
    if not _is_workforce_manager(user):
        raise AuthorizationError("You do not have permission to unlink engineer users")
    tenant_id = _require_engineer_tenant_id(user)
    query = select(Engineer).where(Engineer.id == engineer_id)
    query = apply_tenant_filter(query, Engineer, tenant_id)
    result = await db.execute(query)
    engineer = result.scalar_one_or_none()
    if engineer is None:
        raise NotFoundError("Engineer not found")
    previous = engineer.user_id
    engineer.user_id = None
    await db.commit()
    await db.refresh(engineer)
    logger.info(
        "engineer_user_unlinked engineer_id=%s previous_user_id=%s by_user_id=%s",
        engineer.id,
        previous,
        getattr(user, "id", None),
    )
    return await _engineer_response(db, engineer)


@router.get("/{engineer_id}/competencies", response_model=List[CompetencyRecordResponse])
async def list_engineer_competencies(
    engineer_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """List competency records for an engineer."""
    tenant_id = _require_engineer_tenant_id(user)
    engineer_query = select(Engineer).where(Engineer.id == engineer_id)
    engineer_query = apply_tenant_filter(engineer_query, Engineer, tenant_id)
    engineer_result = await db.execute(engineer_query)
    engineer = engineer_result.scalar_one_or_none()
    if engineer is None:
        raise NotFoundError("Engineer not found")
    _assert_engineer_access(user, engineer, allow_self_read=True)

    query = select(CompetencyRecord).where(CompetencyRecord.engineer_id == engineer_id)
    query = apply_tenant_filter(query, CompetencyRecord, tenant_id)
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
    tenant_id = _require_engineer_tenant_id(user)
    engineer_query = select(Engineer).where(Engineer.id == engineer_id)
    engineer_query = apply_tenant_filter(engineer_query, Engineer, tenant_id)
    engineer_result = await db.execute(engineer_query)
    engineer = engineer_result.scalar_one_or_none()
    if engineer is None:
        raise NotFoundError("Engineer not found")
    _assert_engineer_access(user, engineer, allow_self_read=True)

    query = select(CompetencyRecord).where(CompetencyRecord.engineer_id == engineer_id)
    query = apply_tenant_filter(query, CompetencyRecord, tenant_id)
    result = await db.execute(query)
    records = result.scalars().all()
    if not records:
        return SkillsMatrixResponse(engineer_id=engineer_id, matrix=[])

    latest_records = _latest_competency_records(records)
    asset_type_ids = list({r.asset_type_id for r in latest_records})
    at_query = select(AssetType).where(AssetType.id.in_(asset_type_ids))
    at_query = apply_tenant_filter(at_query, AssetType, tenant_id)
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
