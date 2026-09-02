"""AUD-F3: an answer save that cannot wedge the rest of the audit.

The defect these pin, from AUD-2026-0087: the run held 3.5MB of photos in Azure
storage and **zero** ``audit_responses`` rows. Three things on the save path had
to line up for that to happen, and all three are asserted here:

1. ``POST /runs/{id}/responses`` answered 400 ``duplicate_response`` when a row
   already existed. Non-retryable, and the field client saved questions in a
   sequential loop, so the first duplicate aborted every question after it.
2. There was no way to address an answer by what actually identifies it. The
   client had to decide between insert and update from local state that a failed
   save had already invalidated.
3. Answer writes carried ``If-Match`` on the *run*'s ``updated_at``. Every answer
   bumps it, so one client conflicted with itself and was told the audit had been
   "updated on another device".

Scope of the harness: SQLite here, PostgreSQL in CI. The unique constraint
``uq_audit_responses_run_question`` is built from the models on SQLite, so the
recovery path is real on both. The genuinely concurrent version of the race
cannot be produced from one event loop, so it is provoked directly in
``test_a_lost_insert_race_is_recovered_as_an_update`` by making the pre-read miss
a row that exists — which is exactly what the losing writer sees.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditQuestion, AuditResponse, AuditRun, AuditSection, AuditStatus, AuditTemplate
from tests.conftest import generate_test_reference

TENANT_ID = 1
USER_ID = 1


async def _seed_template(
    session: AsyncSession,
    *,
    tenant_id: int = TENANT_ID,
    question_count: int = 2,
) -> tuple[AuditTemplate, list[AuditQuestion]]:
    template = AuditTemplate(
        name=f"Field technician audit {uuid.uuid4().hex[:8]}",
        category="Safety",
        audit_type="inspection",
        auto_create_findings=False,
        is_published=True,
        is_active=True,
        tenant_id=tenant_id,
        created_by_id=USER_ID,
        version=1,
        reference_number=generate_test_reference("TPL"),
    )
    session.add(template)
    await session.flush()

    section = AuditSection(template_id=template.id, title="Site", sort_order=1)
    session.add(section)
    await session.flush()

    questions = [
        AuditQuestion(
            template_id=template.id,
            section_id=section.id,
            question_text=f"Question {index}",
            question_type="yes_no",
            positive_answer="yes",
            sort_order=index,
        )
        for index in range(1, question_count + 1)
    ]
    session.add_all(questions)
    await session.commit()
    for question in questions:
        await session.refresh(question)
    return template, questions


async def _seed_run(
    session: AsyncSession,
    *,
    tenant_id: int = TENANT_ID,
    status: AuditStatus = AuditStatus.IN_PROGRESS,
    question_count: int = 2,
) -> tuple[AuditRun, list[AuditQuestion]]:
    template, questions = await _seed_template(session, tenant_id=tenant_id, question_count=question_count)
    run = AuditRun(
        template_id=template.id,
        title="AUD-F3 save path",
        status=status,
        tenant_id=tenant_id,
        assigned_to_id=USER_ID,
        created_by_id=USER_ID,
        reference_number=generate_test_reference("AUD"),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run, questions


def _by_question_url(run_id: int, question_id: int) -> str:
    return f"/api/v1/audits/runs/{run_id}/responses/by-question/{question_id}"


async def _rows_for(session: AsyncSession, run_id: int) -> list[AuditResponse]:
    session.expire_all()
    result = await session.execute(select(AuditResponse).where(AuditResponse.run_id == run_id))
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_two_sequential_puts_from_one_client_both_succeed_on_one_row(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """The 400 that used to abort the rest of the loop is now an update."""
    run, questions = await _seed_run(test_session)
    url = _by_question_url(run.id, questions[0].id)

    first = await client.put(url, headers=auth_headers, json={"response_value": "yes"})
    second = await client.put(url, headers=auth_headers, json={"response_value": "no", "notes": "guard missing"})

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["response_value"] == "no"
    assert second.json()["notes"] == "guard missing"

    rows = await _rows_for(test_session, run.id)
    assert len(rows) == 1
    assert rows[0].response_value == "no"
    assert rows[0].tenant_id == TENANT_ID


@pytest.mark.asyncio
async def test_a_failed_question_does_not_stop_the_next_question_saving(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """Server side of the wedge: a refused question leaves the others writable.

    The 404 here stands in for any per-question failure. What matters is that it
    is scoped to the question that failed, so a client saving question by
    question can carry on.
    """
    run, questions = await _seed_run(test_session)
    _, foreign_questions = await _seed_template(test_session)

    refused = await client.put(
        _by_question_url(run.id, foreign_questions[0].id),
        headers=auth_headers,
        json={"response_value": "yes"},
    )
    assert refused.status_code == 404, refused.text

    question_ids = {question.id for question in questions}
    for question_id in sorted(question_ids):
        saved = await client.put(
            _by_question_url(run.id, question_id),
            headers=auth_headers,
            json={"response_value": "yes"},
        )
        assert saved.status_code == 200, saved.text

    rows = await _rows_for(test_session, run.id)
    assert {row.question_id for row in rows} == question_ids


@pytest.mark.asyncio
async def test_a_lower_client_revision_is_a_200_no_op_and_keeps_the_newer_answer(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    run, questions = await _seed_run(test_session)
    url = _by_question_url(run.id, questions[0].id)

    newer = await client.put(
        url,
        headers=auth_headers,
        json={"response_value": "no", "response_json": {"client_revision": 7}},
    )
    assert newer.status_code == 200, newer.text

    late = await client.put(
        url,
        headers=auth_headers,
        json={"response_value": "yes", "response_json": {"client_revision": 3}},
    )

    assert late.status_code == 200, late.text
    assert late.json()["id"] == newer.json()["id"]
    assert late.json()["response_value"] == "no"
    assert late.json()["response_json"] == {"client_revision": 7}

    rows = await _rows_for(test_session, run.id)
    assert len(rows) == 1
    assert rows[0].response_value == "no"


@pytest.mark.asyncio
async def test_an_equal_client_revision_still_applies_so_a_retry_is_not_swallowed(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """A client retrying after a timeout does not know whether its write landed."""
    run, questions = await _seed_run(test_session)
    url = _by_question_url(run.id, questions[0].id)

    await client.put(url, headers=auth_headers, json={"response_value": "no", "response_json": {"client_revision": 4}})
    retried = await client.put(
        url,
        headers=auth_headers,
        json={"response_value": "yes", "response_json": {"client_revision": 4}},
    )

    assert retried.status_code == 200, retried.text
    assert retried.json()["response_value"] == "yes"


@pytest.mark.asyncio
async def test_a_write_with_no_client_revision_is_applied(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """Tolerant reader: a client that has never heard of revisions still saves."""
    run, questions = await _seed_run(test_session)
    url = _by_question_url(run.id, questions[0].id)

    await client.put(url, headers=auth_headers, json={"response_value": "no", "response_json": {"client_revision": 9}})
    unversioned = await client.put(url, headers=auth_headers, json={"response_value": "yes"})

    assert unversioned.status_code == 200, unversioned.text
    assert unversioned.json()["response_value"] == "yes"
    # response_json was not sent, so the stored revision is left alone rather
    # than being blanked by a partial write.
    assert unversioned.json()["response_json"] == {"client_revision": 9}


@pytest.mark.asyncio
async def test_post_duplicate_is_upsert_safe_rather_than_duplicate_response(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """The compatibility route must not wedge a client that still POSTs."""
    run, questions = await _seed_run(test_session)
    url = f"/api/v1/audits/runs/{run.id}/responses"

    created = await client.post(
        url,
        headers=auth_headers,
        json={
            "question_id": questions[0].id,
            "response_value": "yes",
            "notes": "Keep this context",
            "response_json": {"client_revision": 1},
        },
    )
    duplicated = await client.post(
        url,
        headers=auth_headers,
        json={"question_id": questions[0].id, "response_value": "no"},
    )

    assert created.status_code == 201, created.text
    assert duplicated.status_code == 200, duplicated.text
    assert duplicated.json()["id"] == created.json()["id"]
    assert duplicated.json()["response_value"] == "no"
    assert duplicated.json()["notes"] == "Keep this context"
    assert duplicated.json()["response_json"] == {"client_revision": 1}

    rows = await _rows_for(test_session, run.id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_answer_writes_ignore_a_stale_run_token(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """Root cause 3: a single client must not conflict with itself.

    Every answer write bumps ``run.updated_at``, so question 2 always carried
    the token question 1 had just invalidated. A deliberately stale token here
    must not produce 409 on any of the three answer writes.
    """
    run, questions = await _seed_run(test_session)
    stale = {**auth_headers, "If-Match": "2020-01-01T00:00:00+00:00"}

    put = await client.put(
        _by_question_url(run.id, questions[0].id),
        headers=stale,
        json={"response_value": "yes"},
    )
    assert put.status_code == 200, put.text

    post = await client.post(
        f"/api/v1/audits/runs/{run.id}/responses",
        headers=stale,
        json={"question_id": questions[1].id, "response_value": "yes"},
    )
    assert post.status_code == 201, post.text

    patch = await client.patch(
        f"/api/v1/audits/responses/{put.json()['id']}",
        headers=stale,
        json={"response_value": "no"},
    )
    assert patch.status_code == 200, patch.text


@pytest.mark.asyncio
async def test_a_lost_insert_race_is_recovered_as_an_update(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The constraint, not the pre-read, is what makes this safe.

    Simulates the writer that loses the race: its pre-read sees no row, so it
    attempts the insert and the unique constraint refuses it. That must come out
    as an update of the winner's row, not a 500 and not a duplicate.
    """
    from src.api.routes import audits as audits_routes

    run, questions = await _seed_run(test_session)
    url = _by_question_url(run.id, questions[0].id)

    first = await client.put(url, headers=auth_headers, json={"response_value": "yes"})
    assert first.status_code == 200, first.text

    real_answer_row = audits_routes._answer_row
    calls = {"count": 0}

    async def blind_first_read(db, run_id, question_id):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return await real_answer_row(db, run_id, question_id)

    monkeypatch.setattr(audits_routes, "_answer_row", blind_first_read)

    recovered = await client.put(url, headers=auth_headers, json={"response_value": "no", "notes": "second writer"})

    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["id"] == first.json()["id"]
    assert recovered.json()["response_value"] == "no"
    assert recovered.json()["notes"] == "second writer"

    rows = await _rows_for(test_session, run.id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_upsert_auto_starts_a_scheduled_run_like_the_post_path(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    run, questions = await _seed_run(test_session, status=AuditStatus.SCHEDULED)

    saved = await client.put(
        _by_question_url(run.id, questions[0].id),
        headers=auth_headers,
        json={"response_value": "yes"},
    )

    assert saved.status_code == 200, saved.text
    await test_session.refresh(run)
    assert run.status == AuditStatus.IN_PROGRESS
    assert run.started_at is not None


@pytest.mark.asyncio
async def test_upsert_refuses_a_completed_run(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """AUD-F3 does not touch completion; a completed run stays unwritable."""
    run, questions = await _seed_run(test_session, status=AuditStatus.COMPLETED)

    refused = await client.put(
        _by_question_url(run.id, questions[0].id),
        headers=auth_headers,
        json={"response_value": "yes"},
    )

    assert refused.status_code == 400, refused.text
    assert await _rows_for(test_session, run.id) == []


@pytest.mark.asyncio
async def test_upsert_cannot_write_into_another_tenants_run(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    from tests.factories import TenantFactory

    tenant = TenantFactory.build(
        name=f"Other Org {uuid.uuid4().hex[:6]}",
        slug=f"other-org-{uuid.uuid4().hex[:8]}",
        admin_email=f"admin-{uuid.uuid4().hex[:8]}@other.example.com",
        is_active=True,
    )
    test_session.add(tenant)
    await test_session.commit()
    await test_session.refresh(tenant)
    assert tenant.id != TENANT_ID

    run, questions = await _seed_run(test_session, tenant_id=tenant.id)

    refused = await client.put(
        _by_question_url(run.id, questions[0].id),
        headers=auth_headers,
        json={"response_value": "yes"},
    )

    assert refused.status_code == 404, refused.text
    assert await _rows_for(test_session, run.id) == []


@pytest.mark.asyncio
async def test_upsert_scores_the_answer_the_same_way_the_post_path_does(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """A row written by PUT must be countable by the same analytics as a POST row."""
    run, questions = await _seed_run(test_session)

    via_put = await client.put(
        _by_question_url(run.id, questions[0].id),
        headers=auth_headers,
        json={"response_value": "yes"},
    )
    via_post = await client.post(
        f"/api/v1/audits/runs/{run.id}/responses",
        headers=auth_headers,
        json={"question_id": questions[1].id, "response_value": "yes"},
    )

    assert via_put.status_code == 200, via_put.text
    assert via_post.status_code == 201, via_post.text
    assert via_put.json()["score"] == via_post.json()["score"]
    assert via_put.json()["max_score"] == via_post.json()["max_score"]
