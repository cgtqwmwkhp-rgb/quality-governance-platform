"""Competence board API (CB-PR1).

``GET /board?family=pams`` is 404 while ``competence_board_enabled`` is false.
Atlas family is CB-PR3. Live CompetencyDashboard is unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from src.api.dependencies import DbSession, require_permission
from src.api.utils.tenant import require_tenant_id
from src.core.config import settings
from src.domain.models.engineer import Engineer
from src.domain.models.user import User
from src.domain.services.pams_competence_snapshot_service import load_current_snapshot_async, snapshot_stale_reason

DISABLED_DETAIL = "Competence board is not enabled in this environment."
ATLAS_NOT_SHIPPED = "Atlas family ships in CB-PR3."

router = APIRouter()


async def require_competence_board_enabled() -> None:
    if not settings.competence_board_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=DISABLED_DETAIL)


_enabled_router = APIRouter(dependencies=[Depends(require_competence_board_enabled)])


class CompetenceBoardCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issued: bool
    thorough_exam: Optional[bool] = None


class CompetenceBoardColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str


class CompetenceBoardPerson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engineer_id: Optional[int] = None
    pams_technician_id: Optional[int] = None
    display_name: str
    email: Optional[str] = None
    depot: Optional[str] = None
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

    family: Literal["pams"]
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


@_enabled_router.get("/board", response_model=CompetenceBoardResponse)
async def get_competence_board(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("engineer:update"))],
    family: Literal["pams", "atlas"] = Query(..., description="Plant (pams) or statutory (atlas)"),
):
    if family == "atlas":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=ATLAS_NOT_SHIPPED)

    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
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


router.include_router(_enabled_router)
