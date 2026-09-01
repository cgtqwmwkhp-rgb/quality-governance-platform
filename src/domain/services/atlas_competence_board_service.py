"""Atlas family for the competence board (CB-PR3).

Reads the latest training-matrix import. One row per Atlas person, including
people with no engineer_id (Office / Management / Workshop). Never creates a
User. Never joins on display name. Two Atlas people who share an engineer_id
stay as two rows and raise a duplicate banner.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.engineer import Engineer
from src.domain.models.training_matrix import (
    TrainingMatrixCell,
    TrainingMatrixCourse,
    TrainingMatrixImport,
    TrainingMatrixPerson,
)

NO_IMPORT_BANNER = "No Atlas training matrix import yet."
DUPLICATE_BANNER = "Duplicate engineer mapping: {count} Atlas people share an engineer_id. Rows are not merged."


@dataclass(frozen=True)
class AtlasBoardCell:
    issued: bool
    passed_on: Optional[date]
    expires_on: Optional[date]


@dataclass(frozen=True)
class AtlasBoardPerson:
    atlas_person_id: int
    engineer_id: Optional[int]
    display_name: str
    department: Optional[str]
    mapped: bool
    cells: dict[str, AtlasBoardCell]


@dataclass(frozen=True)
class AtlasBoardColumn:
    key: str
    label: str


@dataclass(frozen=True)
class AtlasBoardSnapshot:
    id: Optional[int]
    status: Optional[str]
    source_name: Optional[str]
    row_count: int
    completed_at: Optional[datetime]
    stale: bool
    stale_reason: Optional[str]


@dataclass(frozen=True)
class AtlasBoardView:
    snapshot: AtlasBoardSnapshot
    columns: list[AtlasBoardColumn]
    people: list[AtlasBoardPerson]
    unmapped_count: int
    banner: Optional[str]
    duplicate_engineer_ids: tuple[int, ...]


def empty_atlas_board() -> AtlasBoardView:
    return AtlasBoardView(
        snapshot=AtlasBoardSnapshot(
            id=None,
            status=None,
            source_name=None,
            row_count=0,
            completed_at=None,
            stale=True,
            stale_reason=NO_IMPORT_BANNER,
        ),
        columns=[],
        people=[],
        unmapped_count=0,
        banner=NO_IMPORT_BANNER,
        duplicate_engineer_ids=(),
    )


def assemble_atlas_board(
    *,
    import_row: TrainingMatrixImport,
    people: Sequence[TrainingMatrixPerson],
    courses: Sequence[TrainingMatrixCourse],
    cells: Sequence[TrainingMatrixCell],
    engineers: dict[int, Engineer],
) -> AtlasBoardView:
    """One Atlas person = one board row. Name is never a join key."""
    course_by_id = {course.id: course for course in courses}
    columns_keys: dict[str, str] = {}
    cells_by_person: dict[int, dict[str, AtlasBoardCell]] = {}
    for cell in cells:
        course = course_by_id.get(cell.course_id)
        if course is None:
            continue
        if cell.passed_on is None and cell.expires_on is None:
            continue
        columns_keys[course.course_key] = course.display_name
        person_cells = cells_by_person.setdefault(cell.person_id, {})
        person_cells[course.course_key] = AtlasBoardCell(
            issued=cell.passed_on is not None,
            passed_on=cell.passed_on,
            expires_on=cell.expires_on,
        )

    engineer_counts = Counter(person.engineer_id for person in people if person.engineer_id is not None)
    duplicate_ids = tuple(sorted(eid for eid, count in engineer_counts.items() if count > 1))

    assembled: list[AtlasBoardPerson] = []
    for person in people:
        engineer = engineers.get(person.engineer_id) if person.engineer_id is not None else None
        display = (
            (engineer.display_name if engineer and engineer.display_name else None) or person.atlas_name or "Unnamed"
        )
        assembled.append(
            AtlasBoardPerson(
                atlas_person_id=person.id,
                engineer_id=person.engineer_id,
                display_name=display,
                department=person.department,
                mapped=person.engineer_id is not None,
                cells=cells_by_person.get(person.id, {}),
            )
        )

    assembled.sort(key=lambda row: (not row.mapped, row.display_name.lower()))
    banner = None
    if duplicate_ids:
        banner = DUPLICATE_BANNER.format(count=len(duplicate_ids))

    completed_at = getattr(import_row, "created_at", None) or getattr(import_row, "updated_at", None)
    return AtlasBoardView(
        snapshot=AtlasBoardSnapshot(
            id=import_row.id,
            status=import_row.status,
            source_name=import_row.filename,
            row_count=len(assembled),
            completed_at=completed_at,
            stale=banner is not None,
            stale_reason=banner,
        ),
        columns=[
            AtlasBoardColumn(key=key, label=columns_keys[key]) for key in sorted(columns_keys, key=lambda k: k.lower())
        ],
        people=assembled,
        unmapped_count=sum(1 for row in assembled if not row.mapped),
        banner=banner,
        duplicate_engineer_ids=duplicate_ids,
    )


async def build_atlas_board_async(db: AsyncSession, tenant_id: int) -> AtlasBoardView:
    import_row = (
        await db.execute(
            select(TrainingMatrixImport)
            .where(TrainingMatrixImport.tenant_id == tenant_id)
            .order_by(TrainingMatrixImport.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if import_row is None:
        return empty_atlas_board()

    people = list(
        (
            await db.scalars(
                select(TrainingMatrixPerson).where(
                    TrainingMatrixPerson.tenant_id == tenant_id,
                    TrainingMatrixPerson.last_seen_import_id == import_row.id,
                )
            )
        ).all()
    )
    cells = list(
        (
            await db.scalars(
                select(TrainingMatrixCell).where(
                    TrainingMatrixCell.tenant_id == tenant_id,
                    TrainingMatrixCell.import_id == import_row.id,
                )
            )
        ).all()
    )
    course_ids = {cell.course_id for cell in cells}
    courses: list[TrainingMatrixCourse] = []
    if course_ids:
        courses = list(
            (
                await db.scalars(
                    select(TrainingMatrixCourse).where(
                        TrainingMatrixCourse.tenant_id == tenant_id,
                        TrainingMatrixCourse.id.in_(course_ids),
                    )
                )
            ).all()
        )
    engineer_ids = {person.engineer_id for person in people if person.engineer_id is not None}
    engineers: dict[int, Engineer] = {}
    if engineer_ids:
        engineers = {
            eng.id: eng
            for eng in (
                await db.scalars(select(Engineer).where(Engineer.id.in_(engineer_ids), Engineer.tenant_id == tenant_id))
            ).all()
        }
    return assemble_atlas_board(
        import_row=import_row,
        people=people,
        courses=courses,
        cells=cells,
        engineers=engineers,
    )
