"""Derived Atlas roster delta: appeared / disappeared people needing an operator click.

Does not persist decisions. Atlas person rows are never written here except
``engineer_id`` on create_person (plus the durable name map). Caller commits.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError, ConflictError, NotFoundError, ValidationError
from src.domain.models.engineer import Engineer
from src.domain.models.training_matrix import TrainingMatrixImport, TrainingMatrixPerson
from src.domain.models.user import User
from src.domain.services.training_matrix_compliance import ATLAS_HUB_URL
from src.domain.services.training_matrix_import_service import _ensure_name_map

logger = logging.getLogger(__name__)

RosterAction = Literal["archive", "create_person", "reinstate"]
RosterReason = Literal["unmapped", "archived_person", "left_roster"]
SuggestedAction = Literal["link_person", "create_person", "reinstate", "archive"]


@dataclass
class RosterDeltaItem:
    person_id: int
    atlas_name: str
    department: Optional[str]
    board_role_override: Optional[str]
    first_seen_at: datetime
    new_since_previous_import: bool
    last_seen_import_id: Optional[int]
    last_seen_at: Optional[datetime]
    last_seen_filename: Optional[str]
    reason: RosterReason
    suggested_action: SuggestedAction
    engineer_id: Optional[int]
    engineer_display_name: Optional[str]
    engineer_is_active: Optional[bool]
    engineer_roster_archived_at: Optional[datetime]
    engineer_pams_technician_id: Optional[int]
    user_id: Optional[int]
    user_email: Optional[str]
    user_is_active: Optional[bool]
    user_is_superuser: Optional[bool]
    blocked_reason: Optional[str]


@dataclass
class RosterDelta:
    latest_import_id: Optional[int] = None
    latest_import_filename: Optional[str] = None
    latest_import_at: Optional[datetime] = None
    latest_person_count: int = 0
    previous_import_id: Optional[int] = None
    previous_import_at: Optional[datetime] = None
    appeared: list[RosterDeltaItem] = field(default_factory=list)
    disappeared: list[RosterDeltaItem] = field(default_factory=list)
    appeared_count: int = 0
    appeared_new_this_import: int = 0
    disappeared_count: int = 0
    atlas_hub_url: str = ATLAS_HUB_URL


@dataclass
class RosterActionResult:
    person_id: int
    action: RosterAction
    engineer_id: Optional[int]
    engineer_is_active: Optional[bool]
    engineer_roster_archived_at: Optional[datetime]
    user_id: Optional[int]
    user_is_active: Optional[bool]
    login_disabled: bool
    atlas_person_changed: bool
    message: str


def _empty_delta() -> RosterDelta:
    return RosterDelta()


async def build_roster_delta(db: AsyncSession, tenant_id: int) -> RosterDelta:
    imports = list(
        (
            await db.execute(
                select(TrainingMatrixImport)
                .where(TrainingMatrixImport.tenant_id == tenant_id)
                .order_by(TrainingMatrixImport.id.desc())
            )
        )
        .scalars()
        .all()
    )
    if not imports:
        return _empty_delta()

    latest = imports[0]
    previous = imports[1] if len(imports) > 1 else None
    import_by_id = {row.id: row for row in imports}

    people = list(
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
    latest_person_count = sum(1 for p in people if p.last_seen_import_id == latest.id)

    eng_ids = {p.engineer_id for p in people if p.engineer_id}
    engineers: dict[int, Engineer] = {}
    if eng_ids:
        eng_rows = (
            (await db.execute(select(Engineer).where(Engineer.id.in_(eng_ids), Engineer.tenant_id == tenant_id)))
            .scalars()
            .all()
        )
        for row in eng_rows:
            engineers[row.id] = row

    user_ids = {eng.user_id for eng in engineers.values() if eng.user_id}
    users: dict[int, User] = {}
    if user_ids:
        user_rows = (
            (await db.execute(select(User).where(User.id.in_(user_ids), User.tenant_id == tenant_id))).scalars().all()
        )
        for row in user_rows:
            users[row.id] = row

    appeared: list[RosterDeltaItem] = []
    disappeared: list[RosterDeltaItem] = []
    latest_created = latest.created_at

    for person in people:
        item = _item_for_person(
            person,
            latest_id=latest.id,
            latest_created=latest_created,
            import_by_id=import_by_id,
            engineers=engineers,
            users=users,
        )
        if item is None:
            continue
        if item.reason in ("unmapped", "archived_person"):
            appeared.append(item)
        elif item.reason == "left_roster":
            disappeared.append(item)

    return RosterDelta(
        latest_import_id=latest.id,
        latest_import_filename=latest.filename,
        latest_import_at=latest.created_at,
        latest_person_count=latest_person_count,
        previous_import_id=previous.id if previous else None,
        previous_import_at=previous.created_at if previous else None,
        appeared=appeared,
        disappeared=disappeared,
        appeared_count=len(appeared),
        appeared_new_this_import=sum(1 for row in appeared if row.new_since_previous_import),
        disappeared_count=len(disappeared),
        atlas_hub_url=ATLAS_HUB_URL,
    )


def _item_for_person(
    person: TrainingMatrixPerson,
    *,
    latest_id: int,
    latest_created: datetime,
    import_by_id: dict[int, TrainingMatrixImport],
    engineers: dict[int, Engineer],
    users: dict[int, User],
) -> Optional[RosterDeltaItem]:
    engineer = engineers.get(person.engineer_id) if person.engineer_id else None
    user = users.get(engineer.user_id) if engineer is not None and engineer.user_id else None
    last_imp = import_by_id.get(person.last_seen_import_id) if person.last_seen_import_id else None
    first_seen = person.created_at
    new_this = bool(first_seen and first_seen >= latest_created)

    on_latest = person.last_seen_import_id == latest_id
    stale = person.last_seen_import_id is not None and person.last_seen_import_id != latest_id

    reason: Optional[RosterReason] = None
    suggested: Optional[SuggestedAction] = None
    if on_latest:
        if engineer is None:
            reason, suggested = "unmapped", "create_person"
        elif engineer.roster_archived_at is not None:
            reason, suggested = "archived_person", "reinstate"
    elif stale:
        engineer_live = bool(engineer is not None and engineer.is_active and engineer.roster_archived_at is None)
        user_live = bool(user is not None and user.is_active)
        if engineer_live or user_live:
            reason, suggested = "left_roster", "archive"

    if reason is None or suggested is None:
        return None

    blocked: Optional[str] = None
    if reason == "left_roster" and user is not None and user.is_superuser:
        blocked = "superuser_login"

    return RosterDeltaItem(
        person_id=person.id,
        atlas_name=person.atlas_name,
        department=person.department,
        board_role_override=person.board_role_override,
        first_seen_at=first_seen,
        new_since_previous_import=new_this,
        last_seen_import_id=person.last_seen_import_id,
        last_seen_at=last_imp.created_at if last_imp else None,
        last_seen_filename=last_imp.filename if last_imp else None,
        reason=reason,
        suggested_action=suggested,
        engineer_id=engineer.id if engineer else None,
        engineer_display_name=engineer.display_name if engineer else None,
        engineer_is_active=engineer.is_active if engineer else None,
        engineer_roster_archived_at=engineer.roster_archived_at if engineer else None,
        engineer_pams_technician_id=engineer.pams_technician_id if engineer else None,
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        user_is_active=user.is_active if user else None,
        user_is_superuser=user.is_superuser if user else None,
        blocked_reason=blocked,
    )


async def apply_roster_action(
    db: AsyncSession,
    *,
    tenant_id: int,
    person_id: int,
    action: RosterAction,
    disable_login: bool,
    actor_user_id: int,
) -> RosterActionResult:
    person = (
        await db.execute(
            select(TrainingMatrixPerson).where(
                TrainingMatrixPerson.id == person_id,
                TrainingMatrixPerson.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if person is None:
        raise NotFoundError("Atlas person not found")

    latest = (
        await db.execute(
            select(TrainingMatrixImport)
            .where(TrainingMatrixImport.tenant_id == tenant_id)
            .order_by(TrainingMatrixImport.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    on_latest = bool(latest and person.last_seen_import_id == latest.id)

    if action == "archive":
        return await _archive(
            db,
            person=person,
            tenant_id=tenant_id,
            on_latest=on_latest,
            disable_login=disable_login,
            actor_user_id=actor_user_id,
        )
    if action == "create_person":
        if not on_latest:
            raise ValidationError("Person is not on the current Atlas roster")
        return await _create_person(db, person=person, tenant_id=tenant_id, actor_user_id=actor_user_id)
    if action == "reinstate":
        return await _reinstate(db, person=person, tenant_id=tenant_id, on_latest=on_latest)
    raise ValidationError(f"Unknown roster action: {action}")


async def _load_linked(
    db: AsyncSession, person: TrainingMatrixPerson, tenant_id: int
) -> tuple[Optional[Engineer], Optional[User]]:
    engineer = None
    user = None
    if person.engineer_id:
        engineer = (
            await db.execute(select(Engineer).where(Engineer.id == person.engineer_id, Engineer.tenant_id == tenant_id))
        ).scalar_one_or_none()
    if engineer is not None and engineer.user_id:
        user = (
            await db.execute(select(User).where(User.id == engineer.user_id, User.tenant_id == tenant_id))
        ).scalar_one_or_none()
    return engineer, user


def _snapshot_person(person: TrainingMatrixPerson) -> tuple:
    return (
        person.atlas_name,
        person.department,
        person.board_role_override,
        person.engineer_id,
        person.last_seen_import_id,
    )


async def _archive(
    db: AsyncSession,
    *,
    person: TrainingMatrixPerson,
    tenant_id: int,
    on_latest: bool,
    disable_login: bool,
    actor_user_id: int,
) -> RosterActionResult:
    if on_latest:
        raise ValidationError("still on the Atlas roster; remove the login in Admin → Users")
    before = _snapshot_person(person)
    engineer, user = await _load_linked(db, person, tenant_id)
    if engineer is None and user is None:
        raise ValidationError("nothing_linked")
    if user is not None and user.is_superuser:
        raise BadRequestError("superuser logins must be deactivated from Admin → Users")
    if user is not None and user.id == actor_user_id:
        raise BadRequestError("Cannot deactivate your own account")

    now = datetime.now(timezone.utc)
    login_disabled = False
    if engineer is not None:
        engineer.is_active = False
        engineer.roster_archived_at = now
    if disable_login and user is not None:
        user.is_active = False
        login_disabled = True

    logger.info(
        "roster_archive engineer_id=%s user_id=%s actor=%s login_disabled=%s",
        engineer.id if engineer else None,
        user.id if user else None,
        actor_user_id,
        login_disabled,
    )
    await db.flush()
    if _snapshot_person(person) != before:
        raise ConflictError("Atlas person row must not change on archive")
    return RosterActionResult(
        person_id=person.id,
        action="archive",
        engineer_id=engineer.id if engineer else None,
        engineer_is_active=engineer.is_active if engineer else None,
        engineer_roster_archived_at=engineer.roster_archived_at if engineer else None,
        user_id=user.id if user else None,
        user_is_active=user.is_active if user else None,
        login_disabled=login_disabled,
        atlas_person_changed=False,
        message="Archived. Atlas row unchanged. PAMS and Entra were not written.",
    )


async def _create_person(
    db: AsyncSession,
    *,
    person: TrainingMatrixPerson,
    tenant_id: int,
    actor_user_id: int,
) -> RosterActionResult:
    if person.engineer_id is not None:
        raise ConflictError("Atlas person is already linked to an employee record")
    engineer = Engineer(
        tenant_id=tenant_id,
        display_name=person.atlas_name,
        department=person.department,
        is_active=True,
        user_id=None,
    )
    db.add(engineer)
    await db.flush()
    person.engineer_id = engineer.id
    await _ensure_name_map(
        db,
        tenant_id=tenant_id,
        atlas_name=person.atlas_name,
        engineer_id=engineer.id,
        mapped_by_user_id=actor_user_id,
    )
    logger.info(
        "roster_create_person engineer_id=%s person_id=%s actor=%s",
        engineer.id,
        person.id,
        actor_user_id,
    )
    return RosterActionResult(
        person_id=person.id,
        action="create_person",
        engineer_id=engineer.id,
        engineer_is_active=True,
        engineer_roster_archived_at=None,
        user_id=None,
        user_is_active=None,
        login_disabled=False,
        atlas_person_changed=True,
        message="Person record created with no login. Map or leave unmapped for training only.",
    )


async def _reinstate(
    db: AsyncSession,
    *,
    person: TrainingMatrixPerson,
    tenant_id: int,
    on_latest: bool,
) -> RosterActionResult:
    if not on_latest:
        raise ValidationError("Person is not on the current Atlas roster")
    engineer, user = await _load_linked(db, person, tenant_id)
    if engineer is None:
        raise ValidationError("nothing_linked")
    engineer.roster_archived_at = None
    engineer.is_active = True
    await db.flush()
    return RosterActionResult(
        person_id=person.id,
        action="reinstate",
        engineer_id=engineer.id,
        engineer_is_active=True,
        engineer_roster_archived_at=None,
        user_id=user.id if user else None,
        user_is_active=user.is_active if user else None,
        login_disabled=False,
        atlas_person_changed=False,
        message="Person record reinstated. Login was not re-enabled.",
    )
