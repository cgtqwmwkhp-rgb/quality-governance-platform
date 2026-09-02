"""Compliance-schedule coverage quorum — n of m, per location (CB-PR5).

The schedule carries the *duty* ("this site must maintain at least two
appointed first aiders"). The Atlas competence board carries *who*. This module
joins the two by counting, and never by creating a person-scoped schedule row —
ADR-0020 stays.

Three rules the counting obeys, and one it refuses:

* A person currently covers a role when the latest Atlas import holds a cell for
  a course on that role's allowlist with ``passed_on`` set and either no
  ``expires_on`` or one that has not passed.
* People are counted, not cells: an Atlas person holding both "First Aid" and
  "CPR Awareness / First Aid" is one first aider.
* Unmapped Atlas people (no ``engineer_id``) count. They are appointed people on
  the board; QGP never creates a User for them.
* Location membership is an operator's explicit ``match_department`` string,
  compared exactly. A location called "Workshop" does not match a department
  called "Workshop" by coincidence — with no ``match_department`` the quota is
  ``unknown``, never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Final, Iterable, Optional, Sequence

from sqlalchemy import select

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.competence_coverage_quota import (
    COVERAGE_ROLE_KEYS,
    ROLE_FIRE_MARSHAL,
    ROLE_FIRST_AIDER,
    ROLE_MHFA,
    CompetenceCoverageQuota,
)
from src.domain.models.compliance_schedule import ComplianceRequirementTemplate
from src.domain.models.location import Location
from src.domain.models.training_matrix import (
    TrainingMatrixCell,
    TrainingMatrixCourse,
    TrainingMatrixImport,
    TrainingMatrixPerson,
)
from src.domain.services.atlas_competence_board_service import NO_IMPORT_BANNER
from src.domain.services.training_matrix_parser import normalize_course_key

UNKNOWN_DEPARTMENT_BANNER = "Some quotas have no Atlas department set, so their coverage is unknown."

#: Atlas course labels that count as currency for a role. Written as labels
#: rather than stored keys because that is how an operator reads them; both
#: sides go through ``normalize_course_key`` so "first-aid", "First Aid" and the
#: stored ``first_aid`` are the same course. Explicit allowlist, never a
#: substring or fuzzy match.
ROLE_COURSE_LABELS: Final[dict[str, tuple[str, ...]]] = {
    ROLE_FIRST_AIDER: (
        "first-aid",
        "first aid",
        "cpr awareness",
        "cpr / first aid",
        "cpr awareness / first aid",
    ),
    ROLE_FIRE_MARSHAL: ("fire-marshal", "fire marshal", "fire marshall"),
    ROLE_MHFA: ("mhfa", "mental health first aid", "mental-health-first-aid"),
}

ROLE_COURSE_KEYS: Final[dict[str, frozenset[str]]] = {
    role: frozenset(normalize_course_key(label) for label in labels) for role, labels in ROLE_COURSE_LABELS.items()
}


def _today() -> date:
    return datetime.now(timezone.utc).date()


@dataclass(frozen=True)
class CoverageState:
    """One quota and what the latest Atlas import says about it.

    ``met`` is None — not False — when the answer is unknown, so a missing
    import or an unset department never reads as a failure the site can be
    marked down for.
    """

    quota_id: int
    location_id: int
    role_key: str
    required_n: int
    template_key: str
    match_department: Optional[str]
    current_m: int
    met: Optional[bool]
    gap: bool
    unknown: bool


@dataclass(frozen=True)
class CoverageView:
    items: list[CoverageState]
    banner: Optional[str]


@dataclass(frozen=True)
class AtlasCoverageSnapshot:
    """The latest import's people and cells, or an honest empty."""

    has_import: bool
    people: Sequence[Any]
    courses: Sequence[Any]
    cells: Sequence[Any]


EMPTY_SNAPSHOT = AtlasCoverageSnapshot(has_import=False, people=(), courses=(), cells=())


def role_for_course_key(course_key: str | None) -> Optional[str]:
    """Which coverage role this Atlas course counts toward, if any."""
    if not course_key:
        return None
    normalized = normalize_course_key(course_key)
    for role, keys in ROLE_COURSE_KEYS.items():
        if normalized in keys:
            return role
    return None


def assemble_coverage(
    *,
    quotas: Sequence[CompetenceCoverageQuota],
    snapshot: AtlasCoverageSnapshot,
    today: Optional[date] = None,
) -> list[CoverageState]:
    """Count current cover per quota. Pure — no IO, no clock beyond ``today``."""
    as_of = today or _today()

    roles_by_course_id: dict[int, set[str]] = {}
    for course in snapshot.courses:
        role = role_for_course_key(getattr(course, "course_key", None))
        if role is not None:
            roles_by_course_id.setdefault(course.id, set()).add(role)

    department_by_person: dict[int, Optional[str]] = {person.id: person.department for person in snapshot.people}

    # Sets of person ids, so two matching courses on one person are one person.
    covering: dict[str, set[int]] = {role: set() for role in COVERAGE_ROLE_KEYS}
    for cell in snapshot.cells:
        roles = roles_by_course_id.get(cell.course_id)
        if not roles:
            continue
        if cell.person_id not in department_by_person:
            # A cell from an earlier import, or a person this import dropped.
            continue
        if cell.passed_on is None:
            continue
        if cell.expires_on is not None and cell.expires_on < as_of:
            continue
        for role in roles:
            covering.setdefault(role, set()).add(cell.person_id)

    states: list[CoverageState] = []
    for quota in quotas:
        unknown = (not snapshot.has_import) or quota.match_department is None
        if unknown:
            current_m = 0
            met: Optional[bool] = None
            gap = False
        else:
            current_m = sum(
                1
                for person_id in covering.get(quota.role_key, set())
                if department_by_person.get(person_id) == quota.match_department
            )
            met = current_m >= quota.required_n
            gap = not met
        states.append(
            CoverageState(
                quota_id=quota.id,
                location_id=quota.location_id,
                role_key=quota.role_key,
                required_n=quota.required_n,
                template_key=quota.template_key,
                match_department=quota.match_department,
                current_m=current_m,
                met=met,
                gap=gap,
                unknown=unknown,
            )
        )
    return states


def coverage_banner(*, quotas: Sequence[CompetenceCoverageQuota], snapshot: AtlasCoverageSnapshot) -> Optional[str]:
    if not snapshot.has_import:
        return NO_IMPORT_BANNER
    if any(quota.match_department is None for quota in quotas):
        return UNKNOWN_DEPARTMENT_BANNER
    return None


async def load_atlas_snapshot_async(db: Any, tenant_id: int) -> AtlasCoverageSnapshot:
    """Read the latest Atlas import. No import is an empty answer, not an error."""
    import_row = (
        await db.scalars(
            select(TrainingMatrixImport)
            .where(TrainingMatrixImport.tenant_id == tenant_id)
            .order_by(TrainingMatrixImport.id.desc())
            .limit(1)
        )
    ).first()
    if import_row is None:
        return EMPTY_SNAPSHOT

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
    courses = list(
        (
            await db.scalars(
                select(TrainingMatrixCourse).where(TrainingMatrixCourse.tenant_id == tenant_id),
            )
        ).all()
    )
    return AtlasCoverageSnapshot(has_import=True, people=people, courses=courses, cells=cells)


async def list_quotas_async(db: Any, *, tenant_id: int) -> list[CompetenceCoverageQuota]:
    result = await db.scalars(
        select(CompetenceCoverageQuota)
        .where(CompetenceCoverageQuota.tenant_id == tenant_id)
        .order_by(CompetenceCoverageQuota.location_id, CompetenceCoverageQuota.role_key)
    )
    return list(result.all())


async def build_coverage_view_async(db: Any, tenant_id: int, *, today: Optional[date] = None) -> CoverageView:
    quotas = await list_quotas_async(db, tenant_id=tenant_id)
    if not quotas:
        return CoverageView(items=[], banner=None)
    snapshot = await load_atlas_snapshot_async(db, tenant_id)
    return CoverageView(
        items=assemble_coverage(quotas=quotas, snapshot=snapshot, today=today),
        banner=coverage_banner(quotas=quotas, snapshot=snapshot),
    )


def _worst_first(state: CoverageState) -> tuple[int, int, str]:
    """Order matched quotas so a gap outranks an unknown outranks a met one.

    A requirement is expected to match one quota, but nothing forbids two roles
    pointing at the same template at the same site. Reporting the worst of them
    is deterministic and never invents a summed ``required_n``.
    """
    return (0 if state.gap else 1, 0 if state.unknown else 1, state.role_key)


async def load_coverage_overlay_async(
    db: Any,
    *,
    tenant_id: int,
    targets: Sequence[tuple[int, int, str]],
    today: Optional[date] = None,
) -> dict[int, CoverageState]:
    """Coverage per requirement id for ``(requirement_id, location_id, template_key)``.

    Requirements with no matching quota are absent from the result and keep the
    schedule exactly as it is today.
    """
    if not targets:
        return {}
    location_ids = {location_id for _, location_id, _ in targets}
    quotas = [quota for quota in await list_quotas_async(db, tenant_id=tenant_id) if quota.location_id in location_ids]
    if not quotas:
        return {}
    wanted = {(location_id, template_key) for _, location_id, template_key in targets}
    quotas = [quota for quota in quotas if (quota.location_id, quota.template_key) in wanted]
    if not quotas:
        return {}

    snapshot = await load_atlas_snapshot_async(db, tenant_id)
    by_pair: dict[tuple[int, str], list[CoverageState]] = {}
    for state in assemble_coverage(quotas=quotas, snapshot=snapshot, today=today):
        by_pair.setdefault((state.location_id, state.template_key), []).append(state)

    overlay: dict[int, CoverageState] = {}
    for requirement_id, location_id, template_key in targets:
        matches = by_pair.get((location_id, template_key))
        if not matches:
            continue
        overlay[requirement_id] = sorted(matches, key=_worst_first)[0]
    return overlay


async def _assert_location_in_tenant(db: Any, location_id: int, *, tenant_id: int) -> None:
    """Fail closed: a location in another tenant is simply not found."""
    result = await db.scalars(
        select(Location).where(
            Location.id == location_id,
            Location.tenant_id == tenant_id,
        )
    )
    if result.first() is None:
        raise NotFoundError(f"Location {location_id} not found", code="ENTITY_NOT_FOUND")


async def _assert_template_key_exists(db: Any, template_key: str) -> None:
    """A quota must point at a catalogue row that exists.

    The schedule row is still created by an operator from the catalogue; this
    only refuses a bind to a key nothing can ever activate.
    """
    result = await db.scalars(
        select(ComplianceRequirementTemplate).where(
            ComplianceRequirementTemplate.template_key == template_key,
        )
    )
    if result.first() is None:
        raise NotFoundError(f"Catalogue template '{template_key}' not found", code="ENTITY_NOT_FOUND")


async def get_quota_async(
    db: Any,
    *,
    tenant_id: int,
    location_id: int,
    role_key: str,
) -> Optional[CompetenceCoverageQuota]:
    result = await db.scalars(
        select(CompetenceCoverageQuota).where(
            CompetenceCoverageQuota.tenant_id == tenant_id,
            CompetenceCoverageQuota.location_id == location_id,
            CompetenceCoverageQuota.role_key == role_key,
        )
    )
    return result.first()


async def create_quota_async(
    db: Any,
    *,
    tenant_id: int,
    location_id: int,
    role_key: str,
    required_n: int,
    template_key: str,
    match_department: Optional[str] = None,
) -> tuple[CompetenceCoverageQuota, bool]:
    """Return (row, created). The same (tenant, location, role) twice updates it."""
    if role_key not in COVERAGE_ROLE_KEYS:
        raise ValidationError(f"unknown role_key: {role_key}", code="VALIDATION_ERROR")
    if required_n < 1:
        raise ValidationError("required_n must be at least 1", code="VALIDATION_ERROR")

    key = (template_key or "").strip()
    if not key:
        raise ValidationError("template_key is required", code="VALIDATION_ERROR")
    department = match_department.strip() if isinstance(match_department, str) else None
    if department == "":
        department = None

    await _assert_location_in_tenant(db, location_id, tenant_id=tenant_id)
    await _assert_template_key_exists(db, key)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    existing = await get_quota_async(db, tenant_id=tenant_id, location_id=location_id, role_key=role_key)
    if existing is not None:
        existing.required_n = required_n
        existing.template_key = key
        existing.match_department = department
        existing.updated_at = now
        await db.flush()
        return existing, False

    row = CompetenceCoverageQuota(
        tenant_id=tenant_id,
        location_id=location_id,
        role_key=role_key,
        required_n=required_n,
        template_key=key,
        match_department=department,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    return row, True


async def delete_quota_async(db: Any, *, tenant_id: int, quota_id: int) -> None:
    """Remove the quota. Compliance requirements are untouched."""
    row = await db.get(CompetenceCoverageQuota, quota_id)
    if row is None or row.tenant_id != tenant_id:
        raise NotFoundError("Coverage quota not found", code="ENTITY_NOT_FOUND")
    await db.delete(row)
    await db.flush()


def coverage_targets(requirements: Iterable[Any]) -> list[tuple[int, int, str]]:
    """``(requirement_id, location_id, template_key)`` for active location duties.

    The active + location guards mirror ``is_fra_ocr_eligible`` exactly, and for
    the same reason: they run before ``requirement.template`` is read, so this
    never becomes the first access to an unloaded relationship and never turns a
    response mapper into a lazy load under asyncio. A retired obligation carries
    no coverage either way.
    """
    targets: list[tuple[int, int, str]] = []
    for requirement in requirements:
        if not getattr(requirement, "is_active", True):
            continue
        location_id = getattr(requirement, "location_id", None)
        if location_id is None:
            continue
        template = getattr(requirement, "template", None)
        template_key = getattr(template, "template_key", None) if template is not None else None
        if not template_key:
            continue
        targets.append((requirement.id, location_id, template_key))
    return targets


__all__ = [
    "COVERAGE_ROLE_KEYS",
    "ROLE_COURSE_KEYS",
    "ROLE_COURSE_LABELS",
    "UNKNOWN_DEPARTMENT_BANNER",
    "AtlasCoverageSnapshot",
    "CoverageState",
    "CoverageView",
    "assemble_coverage",
    "build_coverage_view_async",
    "coverage_banner",
    "coverage_targets",
    "create_quota_async",
    "delete_quota_async",
    "list_quotas_async",
    "load_atlas_snapshot_async",
    "load_coverage_overlay_async",
    "role_for_course_key",
]
