"""Training matrix compliance APIs — Atlas export ingest + QGP frequency rules (not an LMS)."""

from __future__ import annotations

from datetime import date, datetime, timezone
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
    TrainingMatrixMatrixUpsertRequest,
    TrainingMatrixMatrixUpsertResponse,
    TrainingMatrixNameMapAutoMatchResponse,
    TrainingMatrixNameMapItem,
    TrainingMatrixNameMapUpsert,
    TrainingMatrixNotifyRequest,
    TrainingMatrixNotifyResponse,
    TrainingMatrixPersonComplianceResponse,
    TrainingMatrixPersonRoleUpdate,
    TrainingMatrixPersonRollup,
    TrainingMatrixRequirementCreate,
    TrainingMatrixRequirementListResponse,
    TrainingMatrixRequirementResponse,
    TrainingMatrixRequirementSeedRequest,
    TrainingMatrixRequirementSeedResponse,
    TrainingMatrixRequirementUpdate,
    TrainingMatrixSummaryResponse,
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
from src.domain.models.user import User
from src.domain.services.email_service import email_service
from src.domain.services.training_matrix_board import (
    BOARD_ROLES,
    build_board_summary,
    is_gap_status,
    normalize_board_role,
    person_rollup,
    resolve_board_role,
)
from src.domain.services.training_matrix_compliance import (
    ATLAS_HUB_URL,
    ComplianceInput,
    evaluate_compliance,
    requirement_matches_engineer,
)
from src.domain.services.training_matrix_import_service import (
    auto_match_training_matrix_names,
    persist_training_matrix_import,
)
from src.domain.services.training_matrix_parser import normalize_person_name, parse_training_matrix_csv
from src.domain.services.training_matrix_requirement_seed import seed_plantexpand_2024_requirements

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


async def _import_response(db: DbSession, imp: TrainingMatrixImport) -> TrainingMatrixImportResponse:
    """Serialize an import row and resolve uploader display fields when present."""
    payload = TrainingMatrixImportResponse.model_validate(imp)
    uploader_id = getattr(imp, "uploaded_by_user_id", None)
    if not uploader_id:
        return payload
    uploader = (await db.execute(select(User).where(User.id == uploader_id))).scalar_one_or_none()
    if not uploader:
        return payload.model_copy(update={"uploaded_by_user_id": uploader_id})
    return payload.model_copy(
        update={
            "uploaded_by_user_id": uploader.id,
            "uploaded_by_name": uploader.full_name,
            "uploaded_by_email": uploader.email,
        }
    )


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
        raise ValidationError(
            "Upload the Atlas Training Matrix Report as CSV (.csv). "
            "Excel (.xlsx) is not accepted — export/save as CSV from Atlas first."
        )
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
    return await _import_response(db, imp)


@router.get("/imports/latest", response_model=TrainingMatrixImportResponse)
async def get_latest_import(db: DbSession, user: CurrentUser):
    _require_manager(user)
    tenant_id = _tenant(user)
    imp = await _latest_import(db, tenant_id)
    if not imp:
        raise NotFoundError("No training matrix import found")
    return await _import_response(db, imp)


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
    latest = await _latest_import(db, tenant_id)
    people_q = select(TrainingMatrixPerson).where(TrainingMatrixPerson.tenant_id == tenant_id)
    if latest:
        people_q = people_q.where(TrainingMatrixPerson.last_seen_import_id == latest.id)
    people = (await db.execute(people_q.order_by(TrainingMatrixPerson.atlas_name))).scalars().all()
    eng_ids = {p.engineer_id for p in people if p.engineer_id}
    eng_names: dict[int, str] = {}
    if eng_ids:
        for eng in (await db.execute(select(Engineer).where(Engineer.id.in_(eng_ids)))).scalars().all():
            eng_names[eng.id] = eng.display_name or f"#{eng.id}"
    return [
        TrainingMatrixNameMapItem(
            person_id=p.id,
            atlas_name=p.atlas_name,
            department=p.department,
            board_role_override=p.board_role_override,
            engineer_id=p.engineer_id,
            engineer_display_name=eng_names.get(p.engineer_id) if p.engineer_id else None,
            mapped=p.engineer_id is not None,
        )
        for p in people
    ]


@router.post("/name-maps/auto-match", response_model=TrainingMatrixNameMapAutoMatchResponse)
async def auto_match_name_maps(db: DbSession, user: CurrentUser):
    """Re-apply saved Atlas→employee maps and unique display-name auto-match."""
    _require_admin(user)
    tenant_id = _tenant(user)
    result = await auto_match_training_matrix_names(
        db,
        tenant_id=tenant_id,
        mapped_by_user_id=getattr(user, "id", None),
        latest_import_only=True,
    )
    await db.commit()
    return TrainingMatrixNameMapAutoMatchResponse(**result)


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
        person_id=person.id if person else None,
        atlas_name=atlas_name,
        department=person.department if person else None,
        board_role_override=person.board_role_override if person else None,
        engineer_id=eng.id,
        engineer_display_name=eng.display_name or f"#{eng.id}",
        mapped=True,
    )


@router.patch("/people/{person_id}", response_model=TrainingMatrixNameMapItem)
async def patch_person_board_role(
    person_id: int,
    db: DbSession,
    user: CurrentUser,
    body: TrainingMatrixPersonRoleUpdate,
):
    """Set or clear the Admin Training group override for an Atlas person."""
    _require_admin(user)
    tenant_id = _tenant(user)
    person = (
        await db.execute(
            select(TrainingMatrixPerson).where(
                TrainingMatrixPerson.id == person_id,
                TrainingMatrixPerson.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not person:
        raise NotFoundError("Atlas person not found")

    if body.board_role_override is None or str(body.board_role_override).strip() == "":
        person.board_role_override = None
    else:
        normalized = normalize_board_role(body.board_role_override)
        if not normalized:
            allowed = ", ".join(BOARD_ROLES)
            raise ValidationError(f"board_role_override must be one of: {allowed}")
        person.board_role_override = normalized

    await db.commit()
    await db.refresh(person)

    eng_name: Optional[str] = None
    if person.engineer_id:
        eng = (await db.execute(select(Engineer).where(Engineer.id == person.engineer_id))).scalar_one_or_none()
        if eng:
            eng_name = eng.display_name or f"#{eng.id}"

    return TrainingMatrixNameMapItem(
        person_id=person.id,
        atlas_name=person.atlas_name,
        department=person.department,
        board_role_override=person.board_role_override,
        engineer_id=person.engineer_id,
        engineer_display_name=eng_name,
        mapped=person.engineer_id is not None,
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


@router.post(
    "/requirements/seed",
    response_model=TrainingMatrixRequirementSeedResponse,
    status_code=status.HTTP_200_OK,
)
async def seed_requirements(
    db: DbSession,
    user: CurrentUser,
    body: TrainingMatrixRequirementSeedRequest,
):
    """Seed requirement rows from a SoR template into the DB (still fully editable)."""
    _require_admin(user)
    tenant_id = _tenant(user)
    if body.template != "plantexpand_2024_v1":
        raise ValidationError("Unknown template. Supported: plantexpand_2024_v1")
    try:
        result = await seed_plantexpand_2024_requirements(db, tenant_id=tenant_id, mode=body.mode)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return TrainingMatrixRequirementSeedResponse(
        template_id=result.template_id,
        template_label=result.template_label,
        created=result.created,
        skipped_existing=result.skipped_existing,
        unmatched_modules=result.unmatched_modules,
        created_without_atlas_match=result.created_without_atlas_match,
    )


@router.post("/requirements/matrix", response_model=TrainingMatrixMatrixUpsertResponse)
async def upsert_requirements_matrix(
    db: DbSession,
    user: CurrentUser,
    body: TrainingMatrixMatrixUpsertRequest,
):
    """Bulk upsert the interactive Admin frequency matrix (dept x course cells).

    A null/0 frequency deactivates the requirement for that department+course
    instead of deleting it, so history/notes are preserved.
    """
    _require_admin(user)
    tenant_id = _tenant(user)

    existing = (
        (
            await db.execute(
                select(TrainingMatrixRequirement).where(
                    TrainingMatrixRequirement.tenant_id == tenant_id,
                    TrainingMatrixRequirement.match_role_key.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    by_key: dict[tuple[str, str], TrainingMatrixRequirement] = {
        ((row.match_department or "").strip().lower(), row.course_key): row for row in existing
    }

    upserted = 0
    deactivated = 0
    for cell in body.cells:
        dept = (cell.match_department or "").strip()
        if not dept or not cell.course_key:
            continue
        key = (dept.lower(), cell.course_key)
        current = by_key.get(key)

        if not cell.frequency_years:
            if current and current.is_active:
                current.is_active = False
                deactivated += 1
            continue

        if current:
            current.frequency_years = cell.frequency_years
            current.course_display_name = cell.course_display_name or current.course_display_name
            current.is_active = True
        else:
            current = TrainingMatrixRequirement(
                tenant_id=tenant_id,
                match_department=dept,
                match_role_key=None,
                course_key=cell.course_key,
                course_display_name=cell.course_display_name or cell.course_key,
                frequency_years=cell.frequency_years,
                is_active=True,
                notes="board:manual",
            )
            db.add(current)
            by_key[key] = current
        upserted += 1

    await db.commit()
    return TrainingMatrixMatrixUpsertResponse(upserted=upserted, deactivated=deactivated)


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
        for engineer_row in (await db.execute(select(Engineer).where(Engineer.id.in_(eng_ids)))).scalars().all():
            engineers[engineer_row.id] = engineer_row

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
        mapped_eng: Optional[Engineer] = engineers.get(person.engineer_id) if person.engineer_id else None
        # Admin Training group wins for requirement matching; else Atlas/employee dept.
        override = normalize_board_role(person.board_role_override)
        eng_dept = (
            override or (mapped_eng.department if mapped_eng and mapped_eng.department else None) or person.department
        )
        eng_title = mapped_eng.job_title if mapped_eng else None
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
                    person_id=person.id,
                    atlas_name=person.atlas_name,
                    department=person.department,
                    board_role_override=person.board_role_override,
                    engineer_id=person.engineer_id,
                    engineer_display_name=(mapped_eng.display_name if mapped_eng else None),
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
                    last_training_notified_at=person.last_training_notified_at,
                )
            )
    return rows, imp.id


@router.get("/summary", response_model=TrainingMatrixSummaryResponse)
async def training_matrix_summary(db: DbSession, user: CurrentUser):
    """Board SSOT: module OK% (hero), people fully OK (caption), horizons, top overdue courses."""
    _require_manager(user)
    tenant_id = _tenant(user)
    rows, import_id = await _build_compliance_rows(db, tenant_id=tenant_id)
    payload = build_board_summary([r.model_dump() for r in rows])
    return TrainingMatrixSummaryResponse(
        module_ok=payload["module_ok"],
        people_fully_ok=payload["people_fully_ok"],
        horizons=payload["horizons"],
        top_overdue_courses=payload["top_overdue_courses"],
        required_row_count=payload["required_row_count"],
        person_count=payload["person_count"],
        import_id=import_id,
        atlas_hub_url=ATLAS_HUB_URL,
    )


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


@router.get("/people/{person_id}/compliance", response_model=TrainingMatrixPersonComplianceResponse)
async def person_compliance(person_id: int, db: DbSession, user: CurrentUser):
    """Person drill-down: profile, rollup, full required module list, email eligibility."""
    _require_manager(user)
    tenant_id = _tenant(user)
    person = (
        await db.execute(
            select(TrainingMatrixPerson).where(
                TrainingMatrixPerson.id == person_id,
                TrainingMatrixPerson.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not person:
        raise NotFoundError("Atlas person not found")

    rows, import_id = await _build_compliance_rows(db, tenant_id=tenant_id)
    person_rows = [r for r in rows if r.person_id == person.id]
    rollup = person_rollup([r.model_dump() for r in person_rows])

    can_email = False
    email_skip_reason: Optional[str] = None
    eng_name = None
    if not person.engineer_id:
        email_skip_reason = "Not mapped to an employee — map in Admin → People mapping."
    else:
        eng = (
            await db.execute(select(Engineer).where(Engineer.id == person.engineer_id, Engineer.tenant_id == tenant_id))
        ).scalar_one_or_none()
        eng_name = eng.display_name if eng else None
        if not eng or not eng.user_id:
            email_skip_reason = "Employee has no linked user login."
        else:
            recipient = (await db.execute(select(User).where(User.id == eng.user_id))).scalar_one_or_none()
            if not recipient or not recipient.email:
                email_skip_reason = "Linked user has no email address."
            elif not any(is_gap_status(r.status) for r in person_rows):
                email_skip_reason = "No open training gaps to notify."
            else:
                can_email = True

    return TrainingMatrixPersonComplianceResponse(
        person_id=person.id,
        atlas_name=person.atlas_name,
        department=person.department,
        board_role_override=person.board_role_override,
        board_role=resolve_board_role(person.department, person.board_role_override),
        engineer_id=person.engineer_id,
        engineer_display_name=eng_name,
        can_email=can_email,
        email_skip_reason=email_skip_reason,
        last_training_notified_at=person.last_training_notified_at,
        rollup=TrainingMatrixPersonRollup(
            complete=int(rollup["complete"]),
            overdue=int(rollup["overdue"]),
            need=int(rollup["need"]),
            total=int(rollup["total"]),
            pct=int(rollup["pct"]),
        ),
        items=person_rows,
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


@router.post("/notify", response_model=TrainingMatrixNotifyResponse)
async def notify_people(
    db: DbSession,
    user: CurrentUser,
    body: TrainingMatrixNotifyRequest,
):
    """Email selected Atlas people their non-OK modules + the Atlas hub link."""
    _require_manager(user)
    tenant_id = _tenant(user)

    names = {normalize_person_name(n) for n in body.atlas_names if n and n.strip()}
    if not names:
        raise ValidationError("Provide at least one atlas_name to notify")

    people = (
        (
            await db.execute(
                select(TrainingMatrixPerson).where(
                    TrainingMatrixPerson.tenant_id == tenant_id,
                    TrainingMatrixPerson.atlas_name.in_(names),
                )
            )
        )
        .scalars()
        .all()
    )

    sent = 0
    skipped = 0
    failed = 0
    for person in people:
        if not person.engineer_id:
            skipped += 1
            continue
        eng = (
            await db.execute(select(Engineer).where(Engineer.id == person.engineer_id, Engineer.tenant_id == tenant_id))
        ).scalar_one_or_none()
        recipient: Optional[User] = None
        if eng and eng.user_id:
            recipient = (await db.execute(select(User).where(User.id == eng.user_id))).scalar_one_or_none()
        if not recipient or not recipient.email:
            skipped += 1
            continue

        rows, _ = await _build_compliance_rows(db, tenant_id=tenant_id, engineer_id=person.engineer_id)
        # Align with board Complete definition: due_soon is in-cycle, not a gap email.
        gaps = [row for row in rows if is_gap_status(row.status)]
        if not gaps:
            skipped += 1
            continue

        ok = await email_service.send_training_gap_notification(
            to=recipient.email,
            display_name=eng.display_name if eng and eng.display_name else person.atlas_name,
            gaps=[
                {
                    "course_display_name": g.course_display_name,
                    "status": g.status,
                    "qgp_due_on": g.qgp_due_on.isoformat() if g.qgp_due_on else None,
                }
                for g in gaps
            ],
            atlas_hub_url=ATLAS_HUB_URL,
            message=body.message,
        )
        if ok:
            person.last_training_notified_at = datetime.now(timezone.utc)
            sent += 1
        else:
            failed += 1

    await db.commit()
    return TrainingMatrixNotifyResponse(sent=sent, skipped=skipped, failed=failed)
