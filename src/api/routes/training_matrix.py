"""Training matrix compliance APIs — Atlas export ingest + QGP frequency rules (not an LMS)."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, File, Query, UploadFile, status
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.training_matrix import (
    TrainingMatrixComplianceListResponse,
    TrainingMatrixComplianceRow,
    TrainingMatrixCourseOption,
    TrainingMatrixImportQaResponse,
    TrainingMatrixImportResponse,
    TrainingMatrixNameMapItem,
    TrainingMatrixNameMapUpsert,
    TrainingMatrixRequirementCreate,
    TrainingMatrixRequirementListResponse,
    TrainingMatrixRequirementResponse,
    TrainingMatrixRequirementUpdate,
)
from src.api.utils.tenant import require_tenant_id
from src.domain.exceptions import AuthorizationError, NotFoundError, ValidationError
from src.domain.models.engineer import Engineer
from src.domain.models.training_matrix import (
    TrainingMatrixCell,
    TrainingMatrixCourse,
    TrainingMatrixImport,
    TrainingMatrixNameMap,
    TrainingMatrixPerson,
    TrainingMatrixRequirement,
)
from src.domain.services.training_matrix_compliance import (
    ATLAS_HUB_URL,
    ComplianceInput,
    evaluate_compliance,
    requirement_matches_engineer,
)
from src.domain.services.training_matrix_import_service import persist_training_matrix_import
from src.domain.services.training_matrix_parser import normalize_person_name, parse_training_matrix_csv

router = APIRouter()


def _tenant(user: CurrentUser) -> int:
    return require_tenant_id(getattr(user, "tenant_id", None))


def _is_admin(user: CurrentUser) -> bool:
    role_names = {r.name.lower() for r in getattr(user, "roles", []) or []}
    return bool(getattr(user, "is_superuser", False) or "admin" in role_names)


def _is_workforce_manager(user: CurrentUser) -> bool:
    role_names = {r.name.lower() for r in getattr(user, "roles", []) or []}
    return bool(
        getattr(user, "is_superuser", False)
        or "admin" in role_names
        or "supervisor" in role_names
        or "manager" in role_names
    )


def _require_admin(user: CurrentUser) -> None:
    if not _is_admin(user):
        raise AuthorizationError("Admin role required to upload or configure the training matrix")


def _require_manager(user: CurrentUser) -> None:
    if not _is_workforce_manager(user):
        raise AuthorizationError("Manager access required for training compliance views")


async def _latest_import(db: DbSession, tenant_id: int) -> Optional[TrainingMatrixImport]:
    return (
        await db.execute(
            select(TrainingMatrixImport)
            .where(TrainingMatrixImport.tenant_id == tenant_id)
            .order_by(TrainingMatrixImport.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@router.post("/imports", response_model=TrainingMatrixImportResponse, status_code=status.HTTP_201_CREATED)
async def upload_training_matrix(
    db: DbSession,
    user: CurrentUser,
    file: UploadFile = File(...),
):
    _require_admin(user)
    tenant_id = _tenant(user)
    filename = file.filename or "training-matrix.csv"
    if not filename.lower().endswith(".csv"):
        raise ValidationError("Upload the Atlas Training Matrix Report as CSV (.csv)")
    raw = await file.read()
    if not raw:
        raise ValidationError("Uploaded file is empty")
    try:
        parsed = parse_training_matrix_csv(raw)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    imp = await persist_training_matrix_import(
        db,
        tenant_id=tenant_id,
        filename=filename,
        uploaded_by_user_id=getattr(user, "id", None),
        parsed=parsed,
    )
    await db.commit()
    await db.refresh(imp)
    return TrainingMatrixImportResponse.model_validate(imp)


@router.get("/imports/latest", response_model=TrainingMatrixImportResponse)
async def get_latest_import(db: DbSession, user: CurrentUser):
    _require_manager(user)
    tenant_id = _tenant(user)
    imp = await _latest_import(db, tenant_id)
    if not imp:
        raise NotFoundError("No training matrix import found")
    return TrainingMatrixImportResponse.model_validate(imp)


@router.get("/imports/latest/qa", response_model=TrainingMatrixImportQaResponse)
async def get_latest_import_qa(db: DbSession, user: CurrentUser):
    _require_manager(user)
    tenant_id = _tenant(user)
    imp = await _latest_import(db, tenant_id)
    if not imp:
        raise NotFoundError("No training matrix import found")
    today = date.today()
    cells = (
        (
            await db.execute(
                select(TrainingMatrixCell).where(
                    TrainingMatrixCell.tenant_id == tenant_id,
                    TrainingMatrixCell.import_id == imp.id,
                )
            )
        )
        .scalars()
        .all()
    )

    all_expiry = [c for c in cells if c.expires_on]
    all_before = sum(1 for c in all_expiry if c.expires_on and c.expires_on < today)
    all_after = sum(1 for c in all_expiry if c.expires_on and c.expires_on > today)
    enp = [c for c in cells if c.expires_on and not c.passed_on]
    enp_before = sum(1 for c in enp if c.expires_on and c.expires_on < today)
    enp_after = sum(1 for c in enp if c.expires_on and c.expires_on > today)
    n_all = len(all_expiry) or 1
    n_enp = len(enp) or 1
    return TrainingMatrixImportQaResponse(
        import_id=imp.id,
        expiry_without_passed_count=len(enp),
        expiry_without_passed_before_today=enp_before,
        expiry_without_passed_after_today=enp_after,
        expiry_without_passed_before_pct=round(100 * enp_before / n_enp, 1) if enp else 0.0,
        expiry_without_passed_after_pct=round(100 * enp_after / n_enp, 1) if enp else 0.0,
        all_expiry_count=len(all_expiry),
        all_expiry_before_today=all_before,
        all_expiry_after_today=all_after,
        all_expiry_before_pct=round(100 * all_before / n_all, 1) if all_expiry else 0.0,
        all_expiry_after_pct=round(100 * all_after / n_all, 1) if all_expiry else 0.0,
    )


@router.get("/courses", response_model=list[TrainingMatrixCourseOption])
async def list_courses(db: DbSession, user: CurrentUser):
    _require_manager(user)
    tenant_id = _tenant(user)
    rows = (
        (
            await db.execute(
                select(TrainingMatrixCourse)
                .where(TrainingMatrixCourse.tenant_id == tenant_id)
                .order_by(TrainingMatrixCourse.display_name)
            )
        )
        .scalars()
        .all()
    )
    return [TrainingMatrixCourseOption(course_key=r.course_key, display_name=r.display_name) for r in rows]


@router.get("/name-maps", response_model=list[TrainingMatrixNameMapItem])
async def list_name_maps(db: DbSession, user: CurrentUser):
    _require_admin(user)
    tenant_id = _tenant(user)
    people = (
        (
            await db.execute(
                select(TrainingMatrixPerson)
                .where(TrainingMatrixPerson.tenant_id == tenant_id)
                .order_by(TrainingMatrixPerson.atlas_name)
            )
        )
        .scalars()
        .all()
    )
    eng_ids = {p.engineer_id for p in people if p.engineer_id}
    eng_names: dict[int, str] = {}
    if eng_ids:
        for eng in (await db.execute(select(Engineer).where(Engineer.id.in_(eng_ids)))).scalars().all():
            eng_names[eng.id] = eng.display_name or f"#{eng.id}"
    return [
        TrainingMatrixNameMapItem(
            atlas_name=p.atlas_name,
            department=p.department,
            engineer_id=p.engineer_id,
            engineer_display_name=eng_names.get(p.engineer_id) if p.engineer_id else None,
            mapped=p.engineer_id is not None,
        )
        for p in people
    ]


@router.put("/name-maps", response_model=TrainingMatrixNameMapItem)
async def upsert_name_map(db: DbSession, user: CurrentUser, body: TrainingMatrixNameMapUpsert):
    _require_admin(user)
    tenant_id = _tenant(user)
    atlas_name = normalize_person_name(body.atlas_name)
    eng = (
        await db.execute(select(Engineer).where(Engineer.id == body.engineer_id, Engineer.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not eng:
        raise NotFoundError("Employee not found")

    existing = (
        await db.execute(
            select(TrainingMatrixNameMap).where(
                TrainingMatrixNameMap.tenant_id == tenant_id,
                TrainingMatrixNameMap.atlas_name == atlas_name,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.engineer_id = eng.id
        existing.mapped_by_user_id = getattr(user, "id", None)
    else:
        db.add(
            TrainingMatrixNameMap(
                tenant_id=tenant_id,
                atlas_name=atlas_name,
                engineer_id=eng.id,
                mapped_by_user_id=getattr(user, "id", None),
            )
        )

    person = (
        await db.execute(
            select(TrainingMatrixPerson).where(
                TrainingMatrixPerson.tenant_id == tenant_id,
                TrainingMatrixPerson.atlas_name == atlas_name,
            )
        )
    ).scalar_one_or_none()
    if person:
        person.engineer_id = eng.id

    await db.commit()
    return TrainingMatrixNameMapItem(
        atlas_name=atlas_name,
        department=person.department if person else None,
        engineer_id=eng.id,
        engineer_display_name=eng.display_name or f"#{eng.id}",
        mapped=True,
    )


@router.get("/requirements", response_model=TrainingMatrixRequirementListResponse)
async def list_requirements(db: DbSession, user: CurrentUser):
    _require_manager(user)
    tenant_id = _tenant(user)
    rows = (
        (
            await db.execute(
                select(TrainingMatrixRequirement)
                .where(TrainingMatrixRequirement.tenant_id == tenant_id)
                .order_by(TrainingMatrixRequirement.id)
            )
        )
        .scalars()
        .all()
    )
    return TrainingMatrixRequirementListResponse(
        items=[TrainingMatrixRequirementResponse.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post(
    "/requirements",
    response_model=TrainingMatrixRequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_requirement(db: DbSession, user: CurrentUser, body: TrainingMatrixRequirementCreate):
    _require_admin(user)
    tenant_id = _tenant(user)
    if not body.match_department and not body.match_role_key:
        raise ValidationError("Provide match_department and/or match_role_key")
    row = TrainingMatrixRequirement(
        tenant_id=tenant_id,
        match_department=body.match_department,
        match_role_key=body.match_role_key,
        course_key=body.course_key,
        course_display_name=body.course_display_name,
        frequency_years=body.frequency_years,
        is_active=body.is_active,
        notes=body.notes,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return TrainingMatrixRequirementResponse.model_validate(row)


@router.patch("/requirements/{requirement_id}", response_model=TrainingMatrixRequirementResponse)
async def update_requirement(
    requirement_id: int,
    db: DbSession,
    user: CurrentUser,
    body: TrainingMatrixRequirementUpdate,
):
    _require_admin(user)
    tenant_id = _tenant(user)
    row = (
        await db.execute(
            select(TrainingMatrixRequirement).where(
                TrainingMatrixRequirement.id == requirement_id,
                TrainingMatrixRequirement.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise NotFoundError("Requirement not found")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return TrainingMatrixRequirementResponse.model_validate(row)


@router.delete("/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_requirement(requirement_id: int, db: DbSession, user: CurrentUser):
    _require_admin(user)
    tenant_id = _tenant(user)
    row = (
        await db.execute(
            select(TrainingMatrixRequirement).where(
                TrainingMatrixRequirement.id == requirement_id,
                TrainingMatrixRequirement.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise NotFoundError("Requirement not found")
    await db.delete(row)
    await db.commit()


async def _build_compliance_rows(
    db: DbSession,
    *,
    tenant_id: int,
    status_filter: Optional[str] = None,
    department: Optional[str] = None,
    engineer_id: Optional[int] = None,
) -> tuple[list[TrainingMatrixComplianceRow], Optional[int]]:
    imp = await _latest_import(db, tenant_id)
    if not imp:
        return [], None

    requirements = (
        (
            await db.execute(
                select(TrainingMatrixRequirement).where(
                    TrainingMatrixRequirement.tenant_id == tenant_id,
                    TrainingMatrixRequirement.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    people = (
        (
            await db.execute(
                select(TrainingMatrixPerson).where(
                    TrainingMatrixPerson.tenant_id == tenant_id,
                    TrainingMatrixPerson.last_seen_import_id == imp.id,
                )
            )
        )
        .scalars()
        .all()
    )
    if engineer_id is not None:
        people = [p for p in people if p.engineer_id == engineer_id]
    if department:
        people = [p for p in people if p.department and department.lower() in p.department.lower()]

    eng_ids = {p.engineer_id for p in people if p.engineer_id}
    engineers: dict[int, Engineer] = {}
    if eng_ids:
        for eng in (await db.execute(select(Engineer).where(Engineer.id.in_(eng_ids)))).scalars().all():
            engineers[eng.id] = eng

    cells = (
        await db.execute(
            select(TrainingMatrixCell, TrainingMatrixCourse)
            .join(TrainingMatrixCourse, TrainingMatrixCourse.id == TrainingMatrixCell.course_id)
            .where(
                TrainingMatrixCell.tenant_id == tenant_id,
                TrainingMatrixCell.import_id == imp.id,
            )
        )
    ).all()
    cell_by_person_course: dict[tuple[int, str], TrainingMatrixCell] = {}
    for cell, course in cells:
        cell_by_person_course[(cell.person_id, course.course_key)] = cell

    rows: list[TrainingMatrixComplianceRow] = []
    for person in people:
        eng = engineers.get(person.engineer_id) if person.engineer_id else None
        eng_dept = (eng.department if eng and eng.department else None) or person.department
        eng_title = eng.job_title if eng else None
        matched_reqs = [
            req
            for req in requirements
            if requirement_matches_engineer(
                match_department=req.match_department,
                match_role_key=req.match_role_key,
                engineer_department=eng_dept,
                engineer_job_title=eng_title,
            )
        ]
        # Deduplicate by course_key (prefer longer frequency if duplicates)
        by_course: dict[str, TrainingMatrixRequirement] = {}
        for req in matched_reqs:
            prev = by_course.get(req.course_key)
            if not prev or req.frequency_years > prev.frequency_years:
                by_course[req.course_key] = req

        for req in by_course.values():
            cell = cell_by_person_course.get((person.id, req.course_key))
            result = evaluate_compliance(
                ComplianceInput(
                    course_key=req.course_key,
                    course_display_name=req.course_display_name,
                    frequency_years=req.frequency_years,
                    atlas_status=cell.atlas_status if cell else None,
                    passed_on=cell.passed_on if cell else None,
                    expires_on=cell.expires_on if cell else None,
                )
            )
            if status_filter and result.status != status_filter:
                continue
            rows.append(
                TrainingMatrixComplianceRow(
                    atlas_name=person.atlas_name,
                    department=person.department,
                    engineer_id=person.engineer_id,
                    engineer_display_name=(eng.display_name if eng else None),
                    course_key=result.course_key,
                    course_display_name=result.course_display_name,
                    frequency_years=result.frequency_years,
                    status=result.status,
                    atlas_status=result.atlas_status,
                    passed_on=result.passed_on,
                    expires_on=result.expires_on,
                    qgp_due_on=result.qgp_due_on,
                    expiry_without_passed=result.expiry_without_passed,
                    atlas_hub_url=ATLAS_HUB_URL,
                )
            )
    return rows, imp.id


@router.get("/compliance", response_model=TrainingMatrixComplianceListResponse)
async def list_compliance(
    db: DbSession,
    user: CurrentUser,
    status_filter: Optional[str] = Query(None, alias="status"),
    department: Optional[str] = None,
):
    _require_manager(user)
    tenant_id = _tenant(user)
    rows, import_id = await _build_compliance_rows(
        db, tenant_id=tenant_id, status_filter=status_filter, department=department
    )
    return TrainingMatrixComplianceListResponse(
        items=rows,
        total=len(rows),
        atlas_hub_url=ATLAS_HUB_URL,
        import_id=import_id,
    )


@router.get("/me", response_model=TrainingMatrixComplianceListResponse)
async def my_training(db: DbSession, user: CurrentUser):
    tenant_id = _tenant(user)
    eng = (
        await db.execute(
            select(Engineer).where(
                Engineer.tenant_id == tenant_id,
                Engineer.user_id == getattr(user, "id", None),
            )
        )
    ).scalar_one_or_none()
    if not eng:
        raise NotFoundError("No employee profile is linked to your user account")
    rows, import_id = await _build_compliance_rows(db, tenant_id=tenant_id, engineer_id=eng.id)
    return TrainingMatrixComplianceListResponse(
        items=rows,
        total=len(rows),
        atlas_hub_url=ATLAS_HUB_URL,
        import_id=import_id,
    )
