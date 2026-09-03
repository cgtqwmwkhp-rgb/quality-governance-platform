"""AUD-F5: who may attach a photo to an audit answer, and what the write leaves.

The generic ``POST /api/v1/evidence-assets/upload`` is gated on
``evidence:create`` — a token held by anyone who may attach a file to any
record. Used for an audit run that means a tenant member can push photos into a
colleague's audit and have them counted as that auditor's evidence, and the
uploader never has to be near the job. The audit-scoped capture endpoint uses
the execute gate instead: the assignee, or ``audit:update``. Both halves are
asserted here, because a gate is only as good as its refusal.

The round trip is asserted too: a 201 must leave a join row, so the question
link exists in the schema rather than only in the client's ``response_json``.
That is the AUD-2026-0087 defect — photos in Azure for run 87 with no
``audit_responses`` row referencing them.

Blob storage is a fake, as in ``test_incident_attachment_roundtrip.py``: this
suite is about the authorisation and the rows, and the write must not depend on
a local ``./storage`` directory existing.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditQuestion, AuditResponse, AuditRun, AuditSection, AuditStatus, AuditTemplate
from src.domain.models.audit_response_evidence import AuditResponseEvidence
from src.domain.models.evidence_asset import EvidenceAsset
from src.main import app
from tests.integration.conftest import _generate_test_jwt

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"guarding photo payload" * 8


def _reference(prefix: str) -> str:
    """A unique reference, without the shared counter.

    ``generate_test_reference`` counts from zero per process, and the
    integration schema is not dropped between PostgreSQL runs, so its output
    collides with the previous run's rows on a developer's database — a failure
    that looks like this suite's bug and is not one. 20 chars is the column.
    """
    return f"{prefix}-F5-{uuid.uuid4().hex[:12]}"


class _FakeStorage:
    """In-memory stand-in so these tests never touch Azure or local disk."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def upload(self, storage_key, content, content_type, metadata=None):
        self.blobs[storage_key] = content
        return storage_key

    async def delete(self, storage_key):
        self.deleted.append(storage_key)
        self.blobs.pop(storage_key, None)
        return True


@pytest.fixture
def fake_storage(monkeypatch):
    storage = _FakeStorage()
    monkeypatch.setattr("src.infrastructure.storage.storage_service", lambda: storage)
    return storage


@pytest.fixture
async def assignee_id(test_session: AsyncSession) -> int:
    """A real ``users`` row, because ``audit_runs.assigned_to_id`` is an FK.

    Its id is not hard-coded: on PostgreSQL the integration schema is not
    dropped between tests, so a fixed id is either taken by another suite's
    leftover row or steals one.
    """
    from src.core.security import get_password_hash
    from tests.factories import UserFactory

    user = UserFactory.build(
        email=f"assignee-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("testpassword123"),
        is_active=True,
        is_superuser=False,
        tenant_id=1,
    )
    test_session.add(user)
    await test_session.commit()
    return user.id


@pytest.fixture
async def assignee_client(assignee_id: int) -> AsyncClient:
    """An auditor with ``audit:read`` only — their authority is the assignment."""
    token = _generate_test_jwt(user_id=str(assignee_id), role="viewer", is_superuser=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client


async def _seed_run(session: AsyncSession, *, assigned_to_id: int | None) -> tuple[int, int]:
    template = AuditTemplate(
        name="AUD-F5 capture",
        category="Safety",
        audit_type="inspection",
        auto_create_findings=False,
        is_published=True,
        is_active=True,
        tenant_id=1,
        created_by_id=1,
        version=1,
        reference_number=_reference("TPL"),
    )
    session.add(template)
    await session.flush()

    section = AuditSection(template_id=template.id, title="Evidence", sort_order=1, weight=1.0)
    session.add(section)
    await session.flush()

    question = AuditQuestion(
        template_id=template.id,
        section_id=section.id,
        question_text="Photograph the guarding",
        question_type="photo",
        is_required=True,
        sort_order=1,
        weight=1.0,
    )
    session.add(question)
    await session.flush()

    run = AuditRun(
        template_id=template.id,
        title="Capture gate run",
        status=AuditStatus.IN_PROGRESS,
        tenant_id=1,
        assigned_to_id=assigned_to_id,
        created_by_id=1,
        reference_number=_reference("AUD"),
    )
    session.add(run)
    await session.commit()

    # Ids snapshotted before anything expires them: attribute access on an
    # expired instance lazy-loads, which MissingGreenlets on asyncpg (AUD-F4).
    run_id = run.id
    question_id = question.id
    return run_id, question_id


@pytest.mark.asyncio
async def test_the_assignee_can_capture_and_the_join_row_is_written(
    assignee_client: AsyncClient,
    assignee_id: int,
    test_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    run_id, question_id = await _seed_run(test_session, assigned_to_id=assignee_id)

    upload = await assignee_client.post(
        f"/api/v1/audits/runs/{run_id}/evidence",
        files={"file": ("guarding.jpg", JPEG_BYTES, "image/jpeg")},
        data={"question_id": str(question_id), "title": "Guarding"},
    )
    assert upload.status_code == 201, upload.text
    receipt = upload.json()
    asset_id = receipt["evidence_asset_id"]
    response_id = receipt["response_id"]
    assert receipt["question_id"] == question_id
    assert receipt["role"] == "photo"
    assert receipt["evidence_asset_ids"] == [asset_id]
    assert list(fake_storage.blobs.values()) == [JPEG_BYTES]

    test_session.expire_all()

    asset = await test_session.get(EvidenceAsset, asset_id)
    assert asset is not None
    assert asset.source_module.value == "audit"
    assert asset.source_id == str(run_id)
    assert asset.description == f"audit_question:{question_id}"
    assert asset.tenant_id == 1

    answer = await test_session.get(AuditResponse, response_id)
    assert answer is not None
    assert answer.run_id == run_id
    assert answer.question_id == question_id
    assert answer.response_json == {"evidence_asset_ids": [asset_id]}

    links = (
        (
            await test_session.execute(
                select(AuditResponseEvidence).where(AuditResponseEvidence.response_id == response_id)
            )
        )
        .scalars()
        .all()
    )
    assert [(link.evidence_asset_id, link.role) for link in links] == [(asset_id, "photo")]


@pytest.mark.asyncio
async def test_a_non_assignee_without_audit_update_is_refused(
    assignee_client: AsyncClient,
    test_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    """Somebody else's run. This is the upload the generic route would allow.

    Assigned to user 1 (the harness's seeded admin) while the caller is the
    ``audit:read`` auditor, so neither half of the execute gate opens.
    """
    run_id, question_id = await _seed_run(test_session, assigned_to_id=1)

    upload = await assignee_client.post(
        f"/api/v1/audits/runs/{run_id}/evidence",
        files={"file": ("guarding.jpg", JPEG_BYTES, "image/jpeg")},
        data={"question_id": str(question_id)},
    )
    assert upload.status_code == 403, upload.text

    # Refused before the blob was written, and nothing was linked.
    assert fake_storage.blobs == {}
    test_session.expire_all()
    answers = (await test_session.execute(select(AuditResponse).where(AuditResponse.run_id == run_id))).scalars().all()
    assert answers == []


@pytest.mark.asyncio
async def test_audit_update_may_capture_for_a_run_it_is_not_assigned(
    client: AsyncClient,
    auth_headers: dict[str, str],
    assignee_id: int,
    test_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    """The other half of the execute gate — a supervisor finishing a run."""
    run_id, question_id = await _seed_run(test_session, assigned_to_id=assignee_id)

    upload = await client.post(
        f"/api/v1/audits/runs/{run_id}/evidence",
        files={"file": ("guarding.jpg", JPEG_BYTES, "image/jpeg")},
        data={"question_id": str(question_id)},
        headers=auth_headers,
    )
    assert upload.status_code == 201, upload.text


@pytest.mark.asyncio
async def test_a_question_from_another_template_is_not_capturable(
    assignee_client: AsyncClient,
    assignee_id: int,
    test_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    """A capture cannot invent a link to a question this run never asked."""
    run_id, _question_id = await _seed_run(test_session, assigned_to_id=assignee_id)
    _other_run_id, other_question_id = await _seed_run(test_session, assigned_to_id=assignee_id)

    upload = await assignee_client.post(
        f"/api/v1/audits/runs/{run_id}/evidence",
        files={"file": ("guarding.jpg", JPEG_BYTES, "image/jpeg")},
        data={"question_id": str(other_question_id)},
    )
    assert upload.status_code == 404, upload.text
    assert fake_storage.blobs == {}


@pytest.mark.asyncio
async def test_a_completed_run_refuses_new_evidence(
    assignee_client: AsyncClient,
    assignee_id: int,
    test_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    """Capture is an answer write, so it stops when answers stop."""
    run_id, question_id = await _seed_run(test_session, assigned_to_id=assignee_id)
    run = await test_session.get(AuditRun, run_id)
    assert run is not None
    run.status = AuditStatus.COMPLETED
    await test_session.commit()

    upload = await assignee_client.post(
        f"/api/v1/audits/runs/{run_id}/evidence",
        files={"file": ("guarding.jpg", JPEG_BYTES, "image/jpeg")},
        data={"question_id": str(question_id)},
    )
    assert upload.status_code == 400, upload.text
    assert fake_storage.blobs == {}


@pytest.mark.asyncio
async def test_an_empty_file_is_refused_before_anything_is_written(
    assignee_client: AsyncClient,
    assignee_id: int,
    test_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    run_id, question_id = await _seed_run(test_session, assigned_to_id=assignee_id)

    upload = await assignee_client.post(
        f"/api/v1/audits/runs/{run_id}/evidence",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
        data={"question_id": str(question_id)},
    )
    assert upload.status_code == 400, upload.text
    assert upload.json()["error"]["code"] == "FILE_TOO_SMALL"
    assert fake_storage.blobs == {}

    test_session.expire_all()
    answers = (await test_session.execute(select(AuditResponse).where(AuditResponse.run_id == run_id))).scalars().all()
    assert answers == []


@pytest.mark.asyncio
async def test_a_failed_link_write_takes_the_blob_back_out(
    assignee_client: AsyncClient,
    assignee_id: int,
    test_session: AsyncSession,
    fake_storage: _FakeStorage,
    monkeypatch,
) -> None:
    """The one ordering this endpoint cannot avoid, and what it owes as a result.

    The blob has to be written before the rows, because a row pointing at a
    blob that was never stored is a broken evidence pack. So when the rows fail,
    the blob must be taken back out — otherwise the storage account slowly fills
    with photos nobody can reach, which is the AUD-2026-0087 shape again with
    the halves swapped.
    """
    run_id, question_id = await _seed_run(test_session, assigned_to_id=assignee_id)

    async def _explode(*_args, **_kwargs):
        raise OperationalError("INSERT", {}, Exception("connection reset"))

    monkeypatch.setattr("src.api.routes.audits._upsert_answer_row", _explode)

    upload = await assignee_client.post(
        f"/api/v1/audits/runs/{run_id}/evidence",
        files={"file": ("guarding.jpg", JPEG_BYTES, "image/jpeg")},
        data={"question_id": str(question_id)},
    )
    assert upload.status_code == 500, upload.text
    assert upload.json()["error"]["code"] == "AUDIT_EVIDENCE_LINK_PERSIST_FAILED"

    assert len(fake_storage.deleted) == 1
    assert fake_storage.blobs == {}

    test_session.expire_all()
    assets = (
        (await test_session.execute(select(EvidenceAsset).where(EvidenceAsset.source_id == str(run_id))))
        .scalars()
        .all()
    )
    answers = (await test_session.execute(select(AuditResponse).where(AuditResponse.run_id == run_id))).scalars().all()
    assert assets == []
    assert answers == []
