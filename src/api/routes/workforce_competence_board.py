"""Competence board API (CB-PR1 / CB-PR3 / CB-PR4).

``GET /board?family=pams|atlas`` is 404 while ``competence_board_enabled`` is false.
Live CompetencyDashboard is unchanged. Atlas never creates a User.

CB-PR4 adds explicit assessment binds and shows the demonstration they produce
over issued plant cells. QGP still never writes PAMS.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from src.api.dependencies import DbSession, require_permission
from src.api.utils.tenant import require_tenant_id
from src.core.config import settings
from src.domain.models.engineer import Engineer
from src.domain.models.user import User
from src.domain.services.atlas_competence_board_service import build_atlas_board_async
from src.domain.services.competence_demonstration_service import (
    PASS_OUTCOME,
    create_bind_async,
    delete_bind_async,
    list_binds_async,
    load_demonstration_overlay_async,
)
from src.domain.services.pams_competence_snapshot_service import load_current_snapshot_async, snapshot_stale_reason

DISABLED_DETAIL = "Competence board is not enabled in this environment."

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
        columns=[CompetenceBoardColumn(key=key, label=key) for key in columns_keys],
        people=people,
        unmapped_count=sum(1 for person in people if not person.mapped),
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


class CompetenceAssessmentBindOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    template_id: int
    characteristic_key: str
    created_at: datetime


class CompetenceAssessmentBindList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CompetenceAssessmentBindOut]


def _serialize_bind(row) -> CompetenceAssessmentBindOut:
    return CompetenceAssessmentBindOut(
        id=row.id,
        template_id=row.template_id,
        characteristic_key=row.characteristic_key,
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
    """Bind one template to one PAMS characteristic. Explicit only — never by name."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    row, created = await create_bind_async(
        db,
        tenant_id=tenant_id,
        template_id=payload.template_id,
        characteristic_key=payload.characteristic_key,
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
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    rows = await list_binds_async(db, tenant_id=tenant_id)
    return CompetenceAssessmentBindList(items=[_serialize_bind(row) for row in rows])


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


router.include_router(_enabled_router)
