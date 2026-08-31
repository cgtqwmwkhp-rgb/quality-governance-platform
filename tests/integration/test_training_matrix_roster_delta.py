"""Atlas roster delta: appeared / disappeared queue and operator actions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from src.core.security import get_password_hash
from src.domain.models.engineer import Engineer
from src.domain.models.training_matrix import TrainingMatrixImport, TrainingMatrixPerson
from src.domain.models.user import User
from src.infrastructure.database import async_session_maker
from tests.factories import TenantFactory, UserFactory

TENANT = 1
DELTA_URL = "/api/v1/training-matrix/roster-delta"
ACTION_URL = "/api/v1/training-matrix/people/{person_id}/roster-action"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _user_count(tenant_id: int = TENANT) -> int:
    async with async_session_maker() as session:
        return int(
            (
                await session.execute(select(func.count()).select_from(User).where(User.tenant_id == tenant_id))
            ).scalar_one()
        )


async def _seed_imports(*, tag: str) -> tuple[int, int]:
    """Insert previous then latest import. Returns (previous_id, latest_id)."""
    async with async_session_maker() as session:
        older = TrainingMatrixImport(
            tenant_id=TENANT,
            filename=f"atlas-prev-{tag}.csv",
            status="completed",
            person_count=1,
        )
        session.add(older)
        await session.flush()
        newer = TrainingMatrixImport(
            tenant_id=TENANT,
            filename=f"atlas-latest-{tag}.csv",
            status="completed",
            person_count=1,
        )
        session.add(newer)
        await session.commit()
        return older.id, newer.id


async def _add_person(
    *,
    atlas_name: str,
    last_seen_import_id: int,
    engineer_id: int | None = None,
    department: str | None = "Mobile Engineers",
) -> int:
    async with async_session_maker() as session:
        person = TrainingMatrixPerson(
            tenant_id=TENANT,
            atlas_name=atlas_name,
            department=department,
            last_seen_import_id=last_seen_import_id,
            engineer_id=engineer_id,
        )
        session.add(person)
        await session.commit()
        return person.id


async def _add_user(*, email: str, is_superuser: bool = False, is_active: bool = True) -> int:
    async with async_session_maker() as session:
        user = UserFactory.build(
            email=email,
            hashed_password=get_password_hash("testpassword123"),
            is_active=is_active,
            is_superuser=is_superuser,
            tenant_id=TENANT,
        )
        session.add(user)
        await session.commit()
        return user.id


async def _add_engineer(
    *,
    display_name: str,
    user_id: int | None = None,
    is_active: bool = True,
    roster_archived_at: datetime | None = None,
    pams_technician_id: int | None = None,
) -> int:
    async with async_session_maker() as session:
        eng = Engineer(
            tenant_id=TENANT,
            display_name=display_name,
            user_id=user_id,
            is_active=is_active,
            roster_archived_at=roster_archived_at,
            pams_technician_id=pams_technician_id,
        )
        session.add(eng)
        await session.commit()
        return eng.id


@pytest.mark.asyncio
async def test_roster_delta_empty_when_no_import(admin_client: AsyncClient):
    response = await admin_client.get(DELTA_URL)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["appeared"] == []
    assert body["disappeared"] == []
    assert body["appeared_count"] == 0
    assert body["disappeared_count"] == 0
    assert body["latest_import_id"] is None


@pytest.mark.asyncio
async def test_viewer_cannot_read_or_act_on_roster(viewer_client: AsyncClient):
    get_res = await viewer_client.get(DELTA_URL)
    assert get_res.status_code == 403, get_res.text
    post_res = await viewer_client.post(
        ACTION_URL.format(person_id=1),
        json={"action": "archive"},
    )
    assert post_res.status_code == 403, post_res.text


@pytest.mark.asyncio
async def test_appeared_unmapped_suggests_create_person(admin_client: AsyncClient):
    tag = "appear"
    _prev, latest = await _seed_imports(tag=tag)
    person_id = await _add_person(atlas_name=f"New Joiner {tag}", last_seen_import_id=latest)

    body = (await admin_client.get(DELTA_URL)).json()
    names = {row["atlas_name"] for row in body["appeared"]}
    assert f"New Joiner {tag}" in names
    row = next(r for r in body["appeared"] if r["person_id"] == person_id)
    assert row["reason"] == "unmapped"
    assert row["suggested_action"] == "create_person"
    assert person_id not in {r["person_id"] for r in body["disappeared"]}


@pytest.mark.asyncio
async def test_stale_unlinked_person_is_on_neither_list(admin_client: AsyncClient):
    """Isabelle shape: left Atlas, nothing linked in QGP — no silent archive row."""
    tag = "isabelle"
    prev, _latest = await _seed_imports(tag=tag)
    person_id = await _add_person(
        atlas_name=f"Left Unlinked {tag}",
        last_seen_import_id=prev,
        engineer_id=None,
    )
    body = (await admin_client.get(DELTA_URL)).json()
    assert person_id not in {r["person_id"] for r in body["appeared"]}
    assert person_id not in {r["person_id"] for r in body["disappeared"]}


@pytest.mark.asyncio
async def test_disappeared_active_engineer_suggests_archive(admin_client: AsyncClient):
    tag = "cameron"
    prev, _latest = await _seed_imports(tag=tag)
    eng_id = await _add_engineer(display_name=f"Leaver {tag}", pams_technician_id=158)
    person_id = await _add_person(
        atlas_name=f"Leaver {tag}",
        last_seen_import_id=prev,
        engineer_id=eng_id,
    )
    body = (await admin_client.get(DELTA_URL)).json()
    row = next(r for r in body["disappeared"] if r["person_id"] == person_id)
    assert row["reason"] == "left_roster"
    assert row["suggested_action"] == "archive"
    assert row["engineer_pams_technician_id"] == 158


@pytest.mark.asyncio
async def test_appeared_archived_person_suggests_reinstate(admin_client: AsyncClient):
    tag = "return"
    _prev, latest = await _seed_imports(tag=tag)
    eng_id = await _add_engineer(
        display_name=f"Returning {tag}",
        is_active=False,
        roster_archived_at=_now(),
    )
    person_id = await _add_person(
        atlas_name=f"Returning {tag}",
        last_seen_import_id=latest,
        engineer_id=eng_id,
    )
    body = (await admin_client.get(DELTA_URL)).json()
    row = next(r for r in body["appeared"] if r["person_id"] == person_id)
    assert row["reason"] == "archived_person"
    assert row["suggested_action"] == "reinstate"


@pytest.mark.asyncio
async def test_archive_inactivates_engineer_and_login_without_touching_atlas(admin_client: AsyncClient):
    tag = "arch"
    prev, _latest = await _seed_imports(tag=tag)
    user_id = await _add_user(email=f"leaver-{tag}@example.com")
    eng_id = await _add_engineer(display_name=f"Archive Me {tag}", user_id=user_id)
    person_id = await _add_person(
        atlas_name=f"Archive Me {tag}",
        last_seen_import_id=prev,
        engineer_id=eng_id,
        department="Workshop",
    )
    users_before = await _user_count()
    res = await admin_client.post(ACTION_URL.format(person_id=person_id), json={"action": "archive"})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["engineer_is_active"] is False
    assert payload["engineer_roster_archived_at"] is not None
    assert payload["login_disabled"] is True
    assert payload["atlas_person_changed"] is False
    assert await _user_count() == users_before

    async with async_session_maker() as session:
        person = await session.get(TrainingMatrixPerson, person_id)
        assert person is not None
        assert person.atlas_name == f"Archive Me {tag}"
        assert person.department == "Workshop"
        assert person.engineer_id == eng_id
        eng = await session.get(Engineer, eng_id)
        user = await session.get(User, user_id)
        assert eng is not None and eng.is_active is False and eng.roster_archived_at is not None
        assert user is not None and user.is_active is False

    delta = (await admin_client.get(DELTA_URL)).json()
    assert person_id not in {r["person_id"] for r in delta["disappeared"]}


@pytest.mark.asyncio
async def test_archive_is_idempotent(admin_client: AsyncClient):
    tag = "idem"
    prev, _latest = await _seed_imports(tag=tag)
    eng_id = await _add_engineer(display_name=f"Twice {tag}")
    person_id = await _add_person(
        atlas_name=f"Twice {tag}",
        last_seen_import_id=prev,
        engineer_id=eng_id,
    )
    first = await admin_client.post(ACTION_URL.format(person_id=person_id), json={"action": "archive"})
    second = await admin_client.post(ACTION_URL.format(person_id=person_id), json={"action": "archive"})
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["engineer_is_active"] is False


@pytest.mark.asyncio
async def test_archive_rejects_still_on_latest(admin_client: AsyncClient):
    tag = "still"
    _prev, latest = await _seed_imports(tag=tag)
    eng_id = await _add_engineer(display_name=f"Still Here {tag}")
    person_id = await _add_person(
        atlas_name=f"Still Here {tag}",
        last_seen_import_id=latest,
        engineer_id=eng_id,
    )
    res = await admin_client.post(ACTION_URL.format(person_id=person_id), json={"action": "archive"})
    assert res.status_code == 422, res.text
    assert "still on the Atlas roster" in res.text


@pytest.mark.asyncio
async def test_archive_rejects_nothing_linked(admin_client: AsyncClient):
    tag = "nolink"
    prev, _latest = await _seed_imports(tag=tag)
    person_id = await _add_person(
        atlas_name=f"Nothing {tag}",
        last_seen_import_id=prev,
    )
    res = await admin_client.post(ACTION_URL.format(person_id=person_id), json={"action": "archive"})
    assert res.status_code == 422, res.text
    assert "nothing_linked" in res.text


@pytest.mark.asyncio
async def test_archive_rejects_superuser_login(admin_client: AsyncClient):
    tag = "su"
    prev, _latest = await _seed_imports(tag=tag)
    person_id = await _add_person(
        atlas_name=f"Super {tag}",
        last_seen_import_id=prev,
        engineer_id=await _add_engineer(display_name=f"Super {tag}", user_id=2),
    )
    res = await admin_client.post(ACTION_URL.format(person_id=person_id), json={"action": "archive"})
    assert res.status_code == 400, res.text
    assert "superuser" in res.text.lower()


@pytest.mark.asyncio
async def test_archive_rejects_self_deactivate(admin_client: AsyncClient):
    tag = "self"
    prev, _latest = await _seed_imports(tag=tag)
    person_id = await _add_person(
        atlas_name=f"Self {tag}",
        last_seen_import_id=prev,
        engineer_id=await _add_engineer(display_name=f"Self {tag}", user_id=1),
    )
    res = await admin_client.post(ACTION_URL.format(person_id=person_id), json={"action": "archive"})
    assert res.status_code == 400, res.text
    assert "own account" in res.text.lower()


@pytest.mark.asyncio
async def test_create_person_does_not_create_a_login(admin_client: AsyncClient):
    tag = "create"
    _prev, latest = await _seed_imports(tag=tag)
    person_id = await _add_person(atlas_name=f"Office Joiner {tag}", last_seen_import_id=latest)
    users_before = await _user_count()
    res = await admin_client.post(
        ACTION_URL.format(person_id=person_id),
        json={"action": "create_person"},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["user_id"] is None
    assert payload["atlas_person_changed"] is True
    assert payload["engineer_id"] is not None
    assert await _user_count() == users_before

    async with async_session_maker() as session:
        person = await session.get(TrainingMatrixPerson, person_id)
        eng = await session.get(Engineer, payload["engineer_id"])
        assert person is not None and person.engineer_id == payload["engineer_id"]
        assert eng is not None and eng.user_id is None and eng.is_active is True

    delta = (await admin_client.get(DELTA_URL)).json()
    assert person_id not in {r["person_id"] for r in delta["appeared"]}

    again = await admin_client.post(
        ACTION_URL.format(person_id=person_id),
        json={"action": "create_person"},
    )
    assert again.status_code == 409, again.text


@pytest.mark.asyncio
async def test_create_person_rejects_leaver(admin_client: AsyncClient):
    tag = "create-left"
    prev, _latest = await _seed_imports(tag=tag)
    person_id = await _add_person(atlas_name=f"Gone {tag}", last_seen_import_id=prev)
    res = await admin_client.post(
        ACTION_URL.format(person_id=person_id),
        json={"action": "create_person"},
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_reinstate_clears_marker_and_does_not_enable_login(admin_client: AsyncClient):
    tag = "rein"
    _prev, latest = await _seed_imports(tag=tag)
    user_id = await _add_user(email=f"back-{tag}@example.com", is_active=False)
    eng_id = await _add_engineer(
        display_name=f"Back {tag}",
        user_id=user_id,
        is_active=False,
        roster_archived_at=_now() - timedelta(days=3),
    )
    person_id = await _add_person(
        atlas_name=f"Back {tag}",
        last_seen_import_id=latest,
        engineer_id=eng_id,
    )
    res = await admin_client.post(
        ACTION_URL.format(person_id=person_id),
        json={"action": "reinstate"},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["engineer_is_active"] is True
    assert payload["engineer_roster_archived_at"] is None
    assert payload["user_is_active"] is False
    assert payload["login_disabled"] is False

    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        assert user is not None and user.is_active is False


@pytest.mark.asyncio
async def test_reinstate_rejects_when_not_on_latest(admin_client: AsyncClient):
    tag = "rein-stale"
    prev, _latest = await _seed_imports(tag=tag)
    eng_id = await _add_engineer(
        display_name=f"Stale {tag}",
        is_active=False,
        roster_archived_at=_now(),
    )
    person_id = await _add_person(
        atlas_name=f"Stale {tag}",
        last_seen_import_id=prev,
        engineer_id=eng_id,
    )
    res = await admin_client.post(
        ACTION_URL.format(person_id=person_id),
        json={"action": "reinstate"},
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_other_tenant_people_do_not_leak_into_delta(admin_client: AsyncClient):
    tag = "tenant"
    _prev, latest = await _seed_imports(tag=tag)
    await _add_person(atlas_name=f"Ours {tag}", last_seen_import_id=latest)
    async with async_session_maker() as session:
        other = TenantFactory.build(name="Other Co", slug=f"other-{tag}")
        session.add(other)
        await session.flush()
        other_id = other.id
        session.add(
            TrainingMatrixImport(
                tenant_id=other_id,
                filename=f"other-{tag}.csv",
                status="completed",
            )
        )
        await session.flush()
        imp_id = (
            await session.execute(
                select(TrainingMatrixImport.id)
                .where(TrainingMatrixImport.tenant_id == other_id)
                .order_by(TrainingMatrixImport.id.desc())
            )
        ).scalar_one()
        session.add(
            TrainingMatrixPerson(
                tenant_id=other_id,
                atlas_name=f"Secret {tag}",
                last_seen_import_id=imp_id,
            )
        )
        await session.commit()

    body = (await admin_client.get(DELTA_URL)).json()
    names = {row["atlas_name"] for row in body["appeared"] + body["disappeared"]}
    assert f"Secret {tag}" not in names
    assert f"Ours {tag}" in names
