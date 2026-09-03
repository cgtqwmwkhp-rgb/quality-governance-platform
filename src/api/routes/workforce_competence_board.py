"""Competence board API (CB-PR1 / CB-PR3 / CB-PR4).

``GET /board?family=pams|atlas`` is 404 while ``competence_board_enabled`` is false.
Live CompetencyDashboard is unchanged. Atlas never creates a User.

CB-PR4 adds explicit assessment binds and shows the demonstration they produce
over issued plant cells. QGP still never writes PAMS.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Optional, get_args

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from src.api.dependencies import DbSession, require_permission

# CB-UI-3 starts a family demonstration by creating an ``AssessmentRun`` on the
# existing create path rather than inventing a second execute shell. Imported at
# module level like `analytics` → `actions`: a deferred import would move an
# import failure from startup to whenever someone first started an assessment.
from src.api.routes.assessments import create_assessment_run
from src.api.schemas.assessment import AssessmentPlantEvidence, AssessmentRunCreate
from src.api.utils.tenant import require_tenant_id
from src.core.config import settings
from src.domain.models.engineer import Engineer
from src.domain.models.user import User
from src.domain.services.atlas_competence_board_service import build_atlas_board_async
from src.domain.services.competence_coverage_service import (
    build_coverage_view_async,
    create_quota_async,
    delete_quota_async,
    list_quotas_async,
)
from src.domain.services.competence_demonstration_service import (
    MAX_INTERVAL_DAYS,
    PASS_OUTCOME,
    create_bind_async,
    delete_bind_async,
    list_binds_async,
    load_demonstration_overlay_async,
)
from src.domain.services.competence_family_start_service import (
    ASSESSOR_HAS_NO_EMPLOYEE_RECORD,
    ASSESSOR_SNAPSHOT_MISSING,
    ENGINEER_NOT_ON_THE_BOARD,
    bound_modes_by_characteristic,
    resolve_assessor_engineer_async,
    resolve_startable_bind_async,
)
from src.domain.services.pams_competence_snapshot_service import load_current_snapshot_async, snapshot_stale_reason

DISABLED_DETAIL = "Competence board is not enabled in this environment."

#: Why no Atlas square offers a start. Statutory training is issued by a course
#: pass held in Atlas, and the binds this slice starts from are PAMS
#: characteristics; there is no Atlas equivalent to bind, so saying so beats
#: rendering an inert control.
ATLAS_START_NOT_APPLICABLE = (
    "Starting a demonstration applies to the Plant family. People courses are issued in Atlas and "
    "QGP records no assessment against them."
)

#: Wire spelling of ``competence_assessment_binds.mode``. Kept in step with
#: ``BIND_MODES`` on the model by a unit test rather than an import, because a
#: Literal cannot be built from a tuple at runtime.
BindMode = Literal["field", "induction"]

#: The wire values of :data:`BindMode`, in the order the picker offers them.
#: Derived from the annotation rather than retyped, so the two cannot drift.
#: ``competence_assessment_binds.mode`` is a plain ``String(16)``, so filtering
#: through this is what keeps a hand-written third value in that column out of
#: the board response instead of leaking it to clients as a startable mode.
BIND_MODE_VALUES: tuple[BindMode, ...] = get_args(BindMode)

router = APIRouter()


async def require_competence_board_enabled() -> None:
    if not settings.competence_board_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=DISABLED_DETAIL)


_enabled_router = APIRouter(dependencies=[Depends(require_competence_board_enabled)])


class CompetenceBoardCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issued: bool
    thorough_exam: Optional[bool] = None
    passed_on: Optional[date] = None
    expires_on: Optional[date] = None
    # CB-PR4 overlay. Absent when no bound assessment has been completed for the
    # cell — never a grey "not_assessed".
    demonstrated: Optional[Literal["pass", "fail"]] = None
    assessed_at: Optional[datetime] = None
    demonstrated_expires_on: Optional[date] = None


class CompetenceBoardColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    # CB-UI-3. Which modes this characteristic can be demonstrated in, from the
    # binds that exist. Empty means *unbound*: the column stays listed and the
    # cell says no family template is mapped yet, which is a gap in QGP's
    # mapping and not a finding against anyone on the row. Always empty for the
    # Atlas family, which has nothing to bind.
    bound_modes: list[BindMode] = Field(default_factory=list)


class CompetenceBoardAssessor(BaseModel):
    """Whether the person *reading* the board could assess on it (CB-UI-3).

    Advisory, so the UI can offer a start only where one would be accepted
    rather than letting the assessor discover a refusal after filling a form.
    It is not the authority: the gate is re-checked server-side on create, and
    a client that ignores this block gets a 403 rather than a run.
    """

    model_config = ConfigDict(extra="forbid")

    engineer_id: Optional[int] = None
    # Characteristics the current PAMS snapshot issues to *this* viewer. Read
    # from the same snapshot the cells are painted from — there is no parallel
    # QGP competence table behind it.
    issued_characteristic_keys: list[str] = Field(default_factory=list)
    blocked_reason: Optional[str] = Field(
        default=None,
        description="Why this viewer cannot assess anything here. Absent when they can.",
    )


class CompetenceBoardPerson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engineer_id: Optional[int] = None
    pams_technician_id: Optional[int] = None
    atlas_person_id: Optional[int] = None
    display_name: str
    email: Optional[str] = None
    depot: Optional[str] = None
    department: Optional[str] = None
    mapped: bool
    cells: dict[str, CompetenceBoardCell]


class CompetenceBoardSnapshotMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Optional[int] = None
    status: Optional[str] = None
    source_name: Optional[str] = None
    row_count: int = 0
    completed_at: Optional[datetime] = None
    stale: bool
    stale_reason: Optional[str] = None


class CompetenceBoardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: Literal["pams", "atlas"]
    snapshot: CompetenceBoardSnapshotMeta
    columns: list[CompetenceBoardColumn]
    people: list[CompetenceBoardPerson]
    unmapped_count: int
    assessor: CompetenceBoardAssessor = Field(default_factory=CompetenceBoardAssessor)
    banner: Optional[str] = Field(
        default=None,
        description="Honest stale/empty notice. Never a grey not_assessed cell.",
    )


def _person_key(
    engineer_id: int | None,
    pams_technician_id: int | None,
    email: str | None,
    name: str | None,
) -> str:
    if engineer_id is not None:
        return f"eng:{engineer_id}"
    if pams_technician_id is not None:
        return f"pams:{pams_technician_id}"
    if email:
        return f"email:{email.lower()}"
    return f"name:{name or 'unknown'}"


async def _attach_demonstrations(
    db: DbSession,
    *,
    tenant_id: int,
    people: list[CompetenceBoardPerson],
) -> None:
    """Overlay the latest bound assessment on issued cells of mapped people.

    Unmapped rows have no engineer to key a demonstration on, so they keep an
    absent overlay. No cell is invented for a characteristic PAMS has not issued.
    """
    engineer_ids = {person.engineer_id for person in people if person.engineer_id is not None}
    overlay = await load_demonstration_overlay_async(db, tenant_id=tenant_id, engineer_ids=engineer_ids)
    if not overlay:
        return
    for person in people:
        if person.engineer_id is None:
            continue
        for characteristic_key, cell in person.cells.items():
            demonstration = overlay.get((person.engineer_id, characteristic_key))
            if demonstration is None:
                continue
            cell.demonstrated = "pass" if demonstration.outcome == PASS_OUTCOME else "fail"
            cell.assessed_at = demonstration.assessed_at
            cell.demonstrated_expires_on = (
                demonstration.expires_at.date() if demonstration.expires_at is not None else None
            )


async def _resolve_board_assessor(
    db: DbSession,
    *,
    tenant_id: int,
    current_user: User,
    rows: list,
) -> CompetenceBoardAssessor:
    """What this viewer is issued on, from the snapshot rows already loaded.

    No extra snapshot read: the issued set is filtered out of the same rows the
    cells are built from, so the board cannot tell the viewer they are issued on
    something the cells disagree about.

    A user with no id (an internal caller passing a bare tenant context) gets
    the blocked answer rather than an unscoped lookup. That is the fail-closed
    reading: no identity means no proof of issuance.
    """
    user_id = getattr(current_user, "id", None)
    assessor = await resolve_assessor_engineer_async(db, tenant_id=tenant_id, user_id=user_id)
    if assessor is None:
        return CompetenceBoardAssessor(blocked_reason=ASSESSOR_HAS_NO_EMPLOYEE_RECORD)
    issued = sorted(
        {row.characteristic_key for row in rows if row.engineer_id == assessor.id and row.characteristic_key}
    )
    return CompetenceBoardAssessor(engineer_id=assessor.id, issued_characteristic_keys=issued)


@_enabled_router.get("/board", response_model=CompetenceBoardResponse)
async def get_competence_board(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("engineer:update"))],
    family: Literal["pams", "atlas"] = Query(..., description="Plant (pams) or statutory (atlas)"),
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    if family == "atlas":
        view = await build_atlas_board_async(db, tenant_id)
        return CompetenceBoardResponse(
            family="atlas",
            snapshot=CompetenceBoardSnapshotMeta(
                id=view.snapshot.id,
                status=view.snapshot.status,
                source_name=view.snapshot.source_name,
                row_count=view.snapshot.row_count,
                completed_at=view.snapshot.completed_at,
                stale=view.snapshot.stale,
                stale_reason=view.snapshot.stale_reason,
            ),
            columns=[CompetenceBoardColumn(key=col.key, label=col.label) for col in view.columns],
            people=[
                CompetenceBoardPerson(
                    engineer_id=person.engineer_id,
                    atlas_person_id=person.atlas_person_id,
                    display_name=person.display_name,
                    department=person.department,
                    mapped=person.mapped,
                    cells={
                        key: CompetenceBoardCell(
                            issued=cell.issued,
                            passed_on=cell.passed_on,
                            expires_on=cell.expires_on,
                        )
                        for key, cell in person.cells.items()
                    },
                )
                for person in view.people
            ],
            unmapped_count=view.unmapped_count,
            assessor=CompetenceBoardAssessor(blocked_reason=ATLAS_START_NOT_APPLICABLE),
            banner=view.banner,
        )

    snapshot, rows = await load_current_snapshot_async(db, tenant_id)

    if snapshot is None:
        return CompetenceBoardResponse(
            family="pams",
            snapshot=CompetenceBoardSnapshotMeta(
                stale=True,
                stale_reason="No PAMS competence snapshot yet.",
            ),
            columns=[],
            people=[],
            unmapped_count=0,
            assessor=CompetenceBoardAssessor(blocked_reason=ASSESSOR_SNAPSHOT_MISSING),
            banner="No PAMS competence snapshot yet.",
        )

    stale_reason = snapshot_stale_reason(snapshot.completed_at)
    engineer_ids = {row.engineer_id for row in rows if row.engineer_id is not None}
    engineers: dict[int, Engineer] = {}
    if engineer_ids:
        engineers = {
            eng.id: eng
            for eng in (
                await db.scalars(select(Engineer).where(Engineer.id.in_(engineer_ids), Engineer.tenant_id == tenant_id))
            ).all()
        }

    columns_keys = sorted({row.characteristic_key for row in rows})
    people_acc: dict[str, CompetenceBoardPerson] = {}
    for row in rows:
        engineer = engineers.get(row.engineer_id) if row.engineer_id is not None else None
        display = (
            (engineer.display_name if engineer and engineer.display_name else None)
            or row.engineer_name
            or (f"Technician #{row.pams_technician_id}" if row.pams_technician_id is not None else "Unmapped person")
        )
        key = _person_key(row.engineer_id, row.pams_technician_id, row.email, display)
        person = people_acc.get(key)
        if person is None:
            person = CompetenceBoardPerson(
                engineer_id=row.engineer_id,
                pams_technician_id=row.pams_technician_id,
                display_name=display,
                email=row.email,
                depot=row.depot,
                mapped=row.engineer_id is not None,
                cells={},
            )
            people_acc[key] = person
        person.cells[row.characteristic_key] = CompetenceBoardCell(
            issued=True,
            thorough_exam=row.thorough_exam,
        )

    people = sorted(people_acc.values(), key=lambda p: (not p.mapped, p.display_name.lower()))
    await _attach_demonstrations(db, tenant_id=tenant_id, people=people)
    bound_modes = bound_modes_by_characteristic(await list_binds_async(db, tenant_id=tenant_id))
    assessor = await _resolve_board_assessor(db, tenant_id=tenant_id, current_user=current_user, rows=rows)
    banner = stale_reason
    return CompetenceBoardResponse(
        family="pams",
        snapshot=CompetenceBoardSnapshotMeta(
            id=snapshot.id,
            status=snapshot.status,
            source_name=snapshot.source_name,
            row_count=snapshot.row_count,
            completed_at=snapshot.completed_at,
            stale=banner is not None,
            stale_reason=banner,
        ),
        columns=[
            CompetenceBoardColumn(
                key=key,
                label=key,
                bound_modes=[mode for mode in BIND_MODE_VALUES if mode in bound_modes.get(key, ())],
            )
            for key in columns_keys
        ],
        people=people,
        unmapped_count=sum(1 for person in people if not person.mapped),
        assessor=assessor,
        banner=banner,
    )


class CompetenceChangeRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: Literal["pams", "atlas"]
    engineer_id: int
    characteristic_key: str = Field(min_length=1, max_length=80)
    action: Literal["issue", "revoke"]
    notes: Optional[str] = Field(default=None, max_length=2000)


class CompetenceChangeRequestOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    family: str
    engineer_id: int
    characteristic_key: str
    action: str
    status: str
    routed_to_email: str
    email_sent: bool
    notes: Optional[str] = None
    created_at: datetime
    closed_at: Optional[datetime] = None
    close_reason: Optional[str] = None


class CompetenceChangeRequestList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CompetenceChangeRequestOut]


def _serialize_change_request(row) -> CompetenceChangeRequestOut:
    return CompetenceChangeRequestOut(
        id=row.id,
        family=row.family,
        engineer_id=row.engineer_id,
        characteristic_key=row.characteristic_key,
        action=row.action,
        status=row.status,
        routed_to_email=row.routed_to_email,
        email_sent=row.email_sent,
        notes=row.notes,
        created_at=row.created_at,
        closed_at=row.closed_at,
        close_reason=row.close_reason,
    )


@_enabled_router.post(
    "/change-requests",
    response_model=CompetenceChangeRequestOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_competence_change_request(
    payload: CompetenceChangeRequestCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("engineer:update"))],
    response: Response,
):
    """Row first. Email second. Never a PAMS write. Atlas family is a mailbox route, not the board."""
    from src.domain.services.competence_change_request_service import (
        CreateChangeRequestInput,
        create_change_request_async,
        try_send_change_request_email,
    )

    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    row, created = await create_change_request_async(
        db,
        tenant_id=tenant_id,
        payload=CreateChangeRequestInput(
            family=payload.family,
            engineer_id=payload.engineer_id,
            characteristic_key=payload.characteristic_key,
            action=payload.action,
            notes=payload.notes,
            created_by_user_id=current_user.id,
        ),
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    await db.commit()
    if created:
        try_send_change_request_email(row)
        await db.commit()
    await db.refresh(row)
    return _serialize_change_request(row)


@_enabled_router.get("/change-requests", response_model=CompetenceChangeRequestList)
async def list_competence_change_requests(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    from src.domain.services.competence_change_request_service import list_change_requests_async

    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    rows = await list_change_requests_async(db, tenant_id=tenant_id)
    await db.commit()
    return CompetenceChangeRequestList(items=[_serialize_change_request(row) for row in rows])


class CompetenceAssessmentBindCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: int
    characteristic_key: str = Field(min_length=1, max_length=80)
    # Defaulted so CB-PR4 callers that predate the field|induction split keep
    # posting a valid body.
    mode: BindMode = "field"
    interval_days: Optional[int] = Field(default=None, ge=1, le=MAX_INTERVAL_DAYS)


class CompetenceAssessmentBindOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    template_id: int
    characteristic_key: str
    mode: str
    # Absent means this bind declares no interval and the demonstration falls
    # back to the CompetencyRequirement resolution. It is not "never expires".
    interval_days: Optional[int] = None
    created_at: datetime


class CompetenceCharacteristicOut(BaseModel):
    """One PAMS characteristic in the current snapshot, bound or not."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str


class CompetenceAssessmentBindList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CompetenceAssessmentBindOut]
    # Every characteristic the snapshot holds, including the ones nobody has
    # bound. An unbound characteristic is a gap in QGP's mapping, not a gap in
    # anyone's competence, so it stays listed rather than being filtered out.
    characteristics: list[CompetenceCharacteristicOut] = Field(default_factory=list)
    banner: Optional[str] = Field(
        default=None,
        description="Honest empty/stale notice for the characteristic inventory.",
    )


def _serialize_bind(row) -> CompetenceAssessmentBindOut:
    return CompetenceAssessmentBindOut(
        id=row.id,
        template_id=row.template_id,
        characteristic_key=row.characteristic_key,
        mode=row.mode or "field",
        interval_days=row.interval_days,
        created_at=row.created_at,
    )


@_enabled_router.post(
    "/assessment-binds",
    response_model=CompetenceAssessmentBindOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_competence_assessment_bind(
    payload: CompetenceAssessmentBindCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("engineer:update"))],
    response: Response,
):
    """Bind one published template to one PAMS characteristic in one mode.

    Explicit only — never by name, and never a PAMS write.
    """
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    row, created = await create_bind_async(
        db,
        tenant_id=tenant_id,
        template_id=payload.template_id,
        characteristic_key=payload.characteristic_key,
        mode=payload.mode,
        interval_days=payload.interval_days,
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    await db.commit()
    await db.refresh(row)
    return _serialize_bind(row)


@_enabled_router.get("/assessment-binds", response_model=CompetenceAssessmentBindList)
async def list_competence_assessment_binds(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """The binds, plus the characteristic inventory they are mapped against.

    Both come from QGP state: the binds from ``competence_assessment_binds`` and
    the inventory from the read-only PAMS snapshot already cached by CB-PR1. No
    PAMS connection is opened here.
    """
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    rows = await list_binds_async(db, tenant_id=tenant_id)
    snapshot, snapshot_rows = await load_current_snapshot_async(db, tenant_id)
    keys = sorted({row.characteristic_key for row in snapshot_rows if row.characteristic_key})
    banner: str | None
    if snapshot is None:
        banner = "No PAMS competence snapshot yet, so there is no characteristic to bind against."
    elif not keys:
        banner = "The current PAMS snapshot holds no characteristics."
    else:
        banner = snapshot_stale_reason(snapshot.completed_at)
    return CompetenceAssessmentBindList(
        items=[_serialize_bind(row) for row in rows],
        characteristics=[CompetenceCharacteristicOut(key=key, label=key) for key in keys],
        banner=banner,
    )


@_enabled_router.delete("/assessment-binds/{bind_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competence_assessment_bind(
    bind_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Revert the bind. Demonstrations already recorded stay as history."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    await delete_bind_async(db, tenant_id=tenant_id, bind_id=bind_id)
    await db.commit()


class CompetencePlantEvidenceIn(BaseModel):
    """Which machine the demonstration happens on. Evidence, never issuance."""

    model_config = ConfigDict(extra="forbid")

    make: Optional[str] = Field(default=None, max_length=120)
    model: Optional[str] = Field(default=None, max_length=120)
    serial: Optional[str] = Field(default=None, max_length=120)
    pams_plant_id: Optional[str] = Field(default=None, max_length=120)


class CompetenceAssessmentStartCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engineer_id: int = Field(ge=1, description="The engineer being assessed (engineers.id)")
    characteristic_key: str = Field(min_length=1, max_length=80)
    # The two modes CB-UI-2 made unique on the bind. There is no third.
    mode: BindMode = "field"
    plant_evidence: Optional[CompetencePlantEvidenceIn] = None


class CompetenceAssessmentStartOut(BaseModel):
    """The run that was created, and the cell it will demonstrate."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    reference_number: str
    template_id: int
    engineer_id: int
    characteristic_key: str
    mode: str
    status: str
    plant_evidence: Optional[dict] = None


@_enabled_router.post(
    "/assessments",
    response_model=CompetenceAssessmentStartOut,
    status_code=status.HTTP_201_CREATED,
    # This route creates an ``AssessmentRun``, so it has to demand what the
    # assessment router demands. Calling ``create_assessment_run`` as a function
    # runs its body but not its ``Depends``, and a board permission must not
    # become a way to create assessments without holding `assessment:create`.
    # Same shape as compliance_schedule's file-to-library route, which declares
    # `document:create` for the write it performs in the other domain.
    dependencies=[Depends(require_permission("assessment:create"))],
)
async def start_competence_assessment(
    payload: CompetenceAssessmentStartCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Start a family demonstration from a plant board cell (CB-UI-3).

    This resolves a *cell* — one person, one PAMS characteristic, one mode — to
    the template CB-UI-2 bound to it, and then creates the run on the existing
    assessment create path. It is deliberately a thin front door rather than a
    second execute shell: ``AssessmentRun`` completion is the only code path
    that writes a ``CompetenceDemonstration``, so the run this returns will hit
    the CB-PR4 overlay on ``POST /api/v1/assessments/{run_id}/complete`` — a
    pass records the demonstration and a fail records FAILED *and* opens the
    IT-Admin revoke change request. No new revoke channel exists here.

    The assessor gate lives on that shared create path, not on this handler, so
    it cannot be walked around by posting a bound ``template_id`` directly.

    QGP never writes PAMS. Nothing on this path opens a PAMS connection, and a
    pass changes no issuance.
    """
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))

    bind = await resolve_startable_bind_async(
        db,
        tenant_id=tenant_id,
        characteristic_key=payload.characteristic_key,
        mode=payload.mode,
    )

    engineer = await db.get(Engineer, payload.engineer_id)
    if engineer is None or engineer.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ENGINEER_NOT_ON_THE_BOARD,
        )

    # The assessor gate is not called here. ``create_assessment_run`` runs it
    # for any bound template and raises 403 with the cell in ``details``, so
    # checking again first would be two extra queries and a second copy of a
    # rule that must have exactly one enforcement point.
    mode = bind.mode or "field"
    run = await create_assessment_run(
        AssessmentRunCreate(
            template_id=bind.template_id,
            engineer_id=payload.engineer_id,
            title=f"{bind.characteristic_key} — {mode} assessment"[:300],
            plant_evidence=(
                AssessmentPlantEvidence(**payload.plant_evidence.model_dump())
                if payload.plant_evidence is not None
                else None
            ),
        ),
        db,
        current_user,
    )
    return CompetenceAssessmentStartOut(
        run_id=run.id,
        reference_number=run.reference_number,
        template_id=run.template_id,
        engineer_id=run.engineer_id,
        characteristic_key=bind.characteristic_key,
        mode=mode,
        status=run.status,
        plant_evidence=run.plant_evidence,
    )


CoverageRoleKey = Literal["first_aider", "fire_marshal", "mhfa"]


class CompetenceCoverageQuotaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: int = Field(ge=1)
    role_key: CoverageRoleKey
    required_n: int = Field(ge=1)
    template_key: str = Field(min_length=1, max_length=80)
    # Explicit Atlas department string. Atlas has no Location foreign key, so
    # leaving this unset makes the quota honestly unknown rather than guessing
    # from the location name.
    match_department: Optional[str] = Field(default=None, max_length=200)


class CompetenceCoverageQuotaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    location_id: int
    role_key: str
    required_n: int
    template_key: str
    match_department: Optional[str] = None
    created_at: datetime


class CompetenceCoverageQuotaList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CompetenceCoverageQuotaOut]


class CompetenceCoverageItem(BaseModel):
    """Counts and location ids only — who holds the role is the board's job."""

    model_config = ConfigDict(extra="forbid")

    quota_id: int
    location_id: int
    role_key: str
    template_key: str
    match_department: Optional[str] = None
    required_n: int
    current_m: int
    met: Optional[bool] = None
    gap: bool
    unknown: bool


class CompetenceCoverageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CompetenceCoverageItem]
    banner: Optional[str] = Field(
        default=None,
        description="Honest empty/unknown notice. No Atlas import means unknown, not zero cover.",
    )


def _serialize_quota(row) -> CompetenceCoverageQuotaOut:
    return CompetenceCoverageQuotaOut(
        id=row.id,
        location_id=row.location_id,
        role_key=row.role_key,
        required_n=row.required_n,
        template_key=row.template_key,
        match_department=row.match_department,
        created_at=row.created_at,
    )


@_enabled_router.get("/coverage", response_model=CompetenceCoverageResponse)
async def get_competence_coverage(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Location coverage quorum (n of m). Never a named person, never a PAMS write."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    view = await build_coverage_view_async(db, tenant_id)
    return CompetenceCoverageResponse(
        items=[
            CompetenceCoverageItem(
                quota_id=state.quota_id,
                location_id=state.location_id,
                role_key=state.role_key,
                template_key=state.template_key,
                match_department=state.match_department,
                required_n=state.required_n,
                current_m=state.current_m,
                met=state.met,
                gap=state.gap,
                unknown=state.unknown,
            )
            for state in view.items
        ],
        banner=view.banner,
    )


@_enabled_router.post(
    "/coverage-quotas",
    response_model=CompetenceCoverageQuotaOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_competence_coverage_quota(
    payload: CompetenceCoverageQuotaCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("engineer:update"))],
    response: Response,
):
    """Declare the duty. It does not create a compliance requirement."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    row, created = await create_quota_async(
        db,
        tenant_id=tenant_id,
        location_id=payload.location_id,
        role_key=payload.role_key,
        required_n=payload.required_n,
        template_key=payload.template_key,
        match_department=payload.match_department,
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    await db.commit()
    await db.refresh(row)
    return _serialize_quota(row)


@_enabled_router.get("/coverage-quotas", response_model=CompetenceCoverageQuotaList)
async def list_competence_coverage_quotas(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Stored configuration only. ``GET /coverage`` is the computed view."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    rows = await list_quotas_async(db, tenant_id=tenant_id)
    return CompetenceCoverageQuotaList(items=[_serialize_quota(row) for row in rows])


@_enabled_router.delete("/coverage-quotas/{quota_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competence_coverage_quota(
    quota_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Drop the duty. Any compliance requirement at that location stays."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    await delete_quota_async(db, tenant_id=tenant_id, quota_id=quota_id)
    await db.commit()


router.include_router(_enabled_router)
