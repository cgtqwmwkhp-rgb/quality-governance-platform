"""Integration tests for the Compliance Schedule Library filing bridge.

ADR-0020 makes filing a separate, explicit step from completing an occurrence.
These tests exercise the route end to end against a real database so that
"the record says filed" is a statement about a committed row rather than about
a mocked session.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.core.config import settings
from src.domain.models.compliance_schedule import ComplianceRequirementTemplate, ComplianceScheduleAnchor
from src.domain.services.compliance_schedule_kill_switch import reset_compliance_schedule_kill_switch_cache
from src.infrastructure.storage import StorageError

FILING_MODULE = "src.domain.services.compliance_schedule_filing_service"


@pytest.fixture
def enable_compliance_schedule(monkeypatch):
    monkeypatch.setattr(settings, "compliance_schedule_enabled", True)
    reset_compliance_schedule_kill_switch_cache()
    yield
    reset_compliance_schedule_kill_switch_cache()


def _cs_headers(permissions: str) -> dict[str, str]:
    from tests.integration.conftest import _generate_test_jwt

    token = _generate_test_jwt(
        user_id="1",
        role="admin",
        is_superuser=False,
        permissions=permissions,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def filing_function(test_session):
    """A `DocumentFunction` with its per-band PEL sequence counters (NS-1).

    The integration harness creates tables from metadata but seeds no library
    reference data, and ``allocate_pel_doc_ref`` refuses a function whose band
    has no counter row — so the counters are part of the fixture, not an
    afterthought. All five cascade bands are seeded, matching what
    ``seed_document_categories`` does in a real environment.
    """
    from src.domain.models.document_library import CASCADE_LEVELS, DocumentFunction, PelDocRefCounter

    suffix = uuid4().hex[:6]
    function = DocumentFunction(
        tenant_id=None,
        code=f"HSEQ{suffix}".upper(),
        name="Health, Safety, Environment & Quality",
        sort_order=10,
        active=True,
    )
    test_session.add(function)
    await test_session.flush()

    for band in CASCADE_LEVELS:
        test_session.add(PelDocRefCounter(function_id=function.id, level_band=band, next_seq=1))
    await test_session.commit()
    await test_session.refresh(function)
    return function


@pytest.fixture
async def filing_category(test_session):
    """A level-2 taxonomy category to file under.

    Since WA-2 the category no longer carries the PEL counter — the reference is
    drawn from the function (see ``filing_function``). The category still
    supplies the filing defaults (access level, statutory flag).
    """
    from src.domain.models.document_library import DocumentCategory

    suffix = uuid4().hex[:6]
    section = DocumentCategory(
        tenant_id=None,
        taxonomy_id=f"03-{suffix}",
        parent_id=None,
        level=1,
        sort_order=3,
        name="Health & Safety",
        slug=f"health-safety-{suffix}",
        ref_prefix="PEL-HSE",
        default_access="all_staff",
        active=True,
    )
    test_session.add(section)
    await test_session.flush()

    subcategory = DocumentCategory(
        tenant_id=None,
        # ``03.`` prefix is what makes ``filing_defaults_for_category`` mark the
        # filed document statutory, which one of the assertions below relies on.
        taxonomy_id=f"03.{suffix}",
        parent_id=section.id,
        level=2,
        sort_order=1,
        name="Fire Safety",
        slug=f"fire-safety-{suffix}",
        ref_prefix=f"PEL-HSE-{suffix}",
        default_access="managers",
        retention_rule="6 years",
        active=True,
    )
    test_session.add(subcategory)
    await test_session.commit()
    await test_session.refresh(subcategory)
    return subcategory


@pytest.fixture
async def unique_template(test_session):
    template = ComplianceRequirementTemplate(
        tenant_id=None,
        template_key=f"file-{uuid4().hex[:12]}",
        title="Fire Risk Assessment",
        taxonomy_id="HS-01",
        description=None,
        regulatory_basis=None,
        frequency_months=12,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=True,
        is_active=True,
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)
    return template


async def _completed_record(client: AsyncClient, headers: dict, template_key: str) -> dict:
    activate = await client.post(
        f"/api/v1/compliance-schedule/catalogue/{template_key}/activate",
        headers=headers,
        json={"next_due_date": "2026-04-01"},
    )
    assert activate.status_code == 201, activate.text
    requirement_id = activate.json()["id"]

    complete = await client.post(
        f"/api/v1/compliance-schedule/requirements/{requirement_id}/records",
        headers=headers,
        json={
            "completed_at": datetime(2026, 4, 2, tzinfo=timezone.utc).isoformat(),
            "check_passed": True,
        },
    )
    assert complete.status_code == 201, complete.text
    return complete.json()


async def _library_document(test_session, *, tenant_id: int = 1, **overrides):
    from src.domain.models.document import Document, FileType
    from src.domain.models.enums import DocumentStatus, DocumentType

    values = dict(
        tenant_id=tenant_id,
        reference_number=f"DOC-2026-{uuid4().hex[:6]}",
        title="Existing FRA report",
        file_name="fra.pdf",
        file_type=FileType.PDF,
        file_size=1024,
        file_path=f"documents/2026/04/{uuid4()}/fra.pdf",
        document_type=DocumentType.RECORD,
        status=DocumentStatus.APPROVED,
        version="1.0",
        access_level="all_staff",
    )
    values.update(overrides)
    document = Document(**values)
    test_session.add(document)
    await test_session.commit()
    await test_session.refresh(document)
    return document


async def _bound_evidence_asset(test_session, *, record_id: int, filename: str = "fra-2026.pdf"):
    from src.domain.models.evidence_asset import EvidenceAsset, EvidenceAssetType, EvidenceSourceModule

    asset = EvidenceAsset(
        tenant_id=1,
        storage_key=f"evidence/compliance_record/{record_id}/{uuid4().hex}_{filename}",
        original_filename=filename,
        content_type="application/pdf",
        file_size_bytes=17,
        asset_type=EvidenceAssetType.PDF,
        source_module=EvidenceSourceModule.COMPLIANCE_RECORD,
        source_id=str(record_id),
        title="FRA 2026 certificate",
    )
    test_session.add(asset)
    await test_session.commit()
    await test_session.refresh(asset)
    return asset


def _fake_storage(monkeypatch, *, download=b"%PDF-1.7 evidence", upload_error: Exception | None = None):
    """Replace the blob backend so filing never touches real storage."""
    storage = MagicMock()
    if isinstance(download, Exception):
        storage.download = AsyncMock(side_effect=download)
    else:
        storage.download = AsyncMock(return_value=download)
    storage.upload = AsyncMock(side_effect=upload_error) if upload_error else AsyncMock(return_value=None)
    monkeypatch.setattr(f"{FILING_MODULE}.storage_service", lambda: storage)
    return storage


# ---------------------------------------------------------------------------
# Gate and authorisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filing_route_is_404_when_the_module_is_off(client: AsyncClient, auth_headers: dict, monkeypatch):
    monkeypatch.setattr(settings, "compliance_schedule_enabled", False)
    reset_compliance_schedule_kill_switch_cache()
    response = await client.post(
        "/api/v1/compliance-schedule/records/1/file",
        headers=auth_headers,
        json={"library_document_id": 1},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_filing_requires_compliance_schedule_update(client: AsyncClient, enable_compliance_schedule):
    headers = _cs_headers("compliance_schedule:read,document:create")
    response = await client.post(
        "/api/v1/compliance-schedule/records/1/file",
        headers=headers,
        json={"library_document_id": 1},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_filing_requires_document_create(client: AsyncClient, enable_compliance_schedule):
    """Filing puts something in the Library, so Library write rights are needed."""
    headers = _cs_headers("compliance_schedule:read,compliance_schedule:update")
    response = await client.post(
        "/api/v1/compliance-schedule/records/1/file",
        headers=headers,
        json={"library_document_id": 1},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"evidence_asset_id": 1, "library_document_id": 2},
        {"evidence_asset_id": 1},
        {"library_document_id": 2, "category_id": 3},
        {"library_document_id": 2, "title": "Renamed"},
        {"evidence_asset_id": 1, "category_id": 2, "unexpected": True},
    ],
    ids=[
        "no-mode",
        "both-modes",
        "evidence-without-category",
        "link-with-category",
        "link-with-title",
        "unknown-field",
    ],
)
async def test_ambiguous_filing_requests_are_rejected(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
    body: dict,
):
    response = await client.post(
        "/api/v1/compliance-schedule/records/1/file",
        headers=superuser_auth_headers,
        json=body,
    )
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# ADR-0020: completing does not file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_completing_an_occurrence_files_nothing(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    superuser_auth_headers: dict,
):
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    assert record["filing_status"] == "not_filed"
    assert record["library_document_id"] is None
    assert record["filing_error"] is None


# ---------------------------------------------------------------------------
# Link mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_linking_an_existing_document_files_the_occurrence(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    superuser_auth_headers: dict,
    test_session,
):
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    document = await _library_document(test_session)

    response = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={"library_document_id": document.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["linked_existing"] is True
    assert body["library_document_id"] == document.id
    assert body["record"]["filing_status"] == "filed"
    assert body["record"]["library_document_id"] == document.id

    # Committed, not merely returned.
    reread = await client.get(
        f"/api/v1/compliance-schedule/records/{record['id']}",
        headers=superuser_auth_headers,
    )
    assert reread.json()["filing_status"] == "filed"


@pytest.mark.asyncio
async def test_filing_twice_is_refused(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    superuser_auth_headers: dict,
    test_session,
):
    """Otherwise the second filing silently orphans the first document."""
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    first = await _library_document(test_session)
    second = await _library_document(test_session, title="Another FRA report")

    ok = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={"library_document_id": first.id},
    )
    assert ok.status_code == 200, ok.text

    again = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={"library_document_id": second.id},
    )
    assert again.status_code == 409, again.text

    reread = await client.get(
        f"/api/v1/compliance-schedule/records/{record['id']}",
        headers=superuser_auth_headers,
    )
    assert reread.json()["library_document_id"] == first.id


@pytest.mark.asyncio
async def test_linking_a_document_from_another_tenant_is_not_found(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    superuser_auth_headers: dict,
    test_session,
):
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    from src.domain.models.tenant import Tenant

    suffix = uuid4().hex[:6]
    other = Tenant(
        name=f"Other {suffix}",
        slug=f"other-{suffix}",
        admin_email=f"admin-{suffix}@example.test",
    )
    test_session.add(other)
    await test_session.commit()
    await test_session.refresh(other)

    foreign = await _library_document(test_session, tenant_id=other.id)

    response = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={"library_document_id": foreign.id},
    )
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# Evidence-promotion mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filing_evidence_creates_a_library_document(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    filing_category,
    filing_function,
    superuser_auth_headers: dict,
    test_session,
    monkeypatch,
):
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    asset = await _bound_evidence_asset(test_session, record_id=record["id"])
    storage = _fake_storage(monkeypatch)

    response = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={
            "evidence_asset_id": asset.id,
            "category_id": filing_category.id,
            "function_code": filing_function.code,
            "cascade_level": 5,
            "title": "Wickford FRA 2026",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["linked_existing"] is False
    assert body["record"]["filing_status"] == "filed"
    # WA-2 / ADR-0023: the reference comes from the function, not the category
    # path. NS-1: and it is banded by cascade level, so a filed record reads
    # `-5001` (band 5 = Form/Register/Record), never the withdrawn `-0001`.
    assert body["pel_doc_ref"] == f"PEL-{filing_function.code}-5001"

    storage.download.assert_awaited_once_with(asset.storage_key)
    # The Library copy is a new key, not a second pointer at the evidence blob:
    # evidence retention and Library retention are different rules.
    written_key = storage.upload.await_args.kwargs["storage_key"]
    assert written_key.startswith("documents/")
    assert written_key != asset.storage_key

    from src.domain.models.document import Document

    document = await test_session.get(Document, body["library_document_id"])
    await test_session.refresh(document)
    assert document.tenant_id == 1
    assert document.title == "Wickford FRA 2026"
    assert document.category_id == filing_category.id
    # Category and Function are different axes and both are recorded (ADR-0023).
    assert document.function_id == filing_function.id
    # ``filing_defaults_for_category`` supplies both of these.
    assert document.access_level == "managers"
    assert document.is_statutory is True
    # Filing puts evidence in the Library; it does not approve or publish it.
    assert document.status.value == "draft"


@pytest.mark.asyncio
async def test_filing_without_a_function_files_the_document_with_no_pel_reference(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    filing_category,
    superuser_auth_headers: dict,
    test_session,
    monkeypatch,
):
    """ADR-0023 fails closed: no confirmed function means no reference, not a guessed one.

    A reference is immutable once issued, so deriving one from the category
    would print a wrong prefix that can never be corrected in place. The
    document is still filed and still openable — it simply leads with its
    DOC-YYYY-#### reference until a function is confirmed.
    """
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    asset = await _bound_evidence_asset(test_session, record_id=record["id"])
    _fake_storage(monkeypatch)

    response = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={"evidence_asset_id": asset.id, "category_id": filing_category.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record"]["filing_status"] == "filed"
    assert body["pel_doc_ref"] is None

    from src.domain.models.document import Document

    document = await test_session.get(Document, body["library_document_id"])
    await test_session.refresh(document)
    assert document.pel_doc_ref is None
    assert document.function_id is None
    assert document.reference_number.startswith("DOC-")


@pytest.mark.asyncio
async def test_filing_with_an_unknown_function_code_is_refused(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    filing_category,
    superuser_auth_headers: dict,
    test_session,
    monkeypatch,
):
    """An unrecognised code must fail loudly, never fall through to "no function"."""
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    asset = await _bound_evidence_asset(test_session, record_id=record["id"])
    _fake_storage(monkeypatch)

    response = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={
            "evidence_asset_id": asset.id,
            "category_id": filing_category.id,
            "function_code": "NOT-A-FUNCTION",
            # Supplied so this exercises the unknown-code path; without it the
            # NS-1 schema rule would reject the request first and this test
            # would pass for the wrong reason.
            "cascade_level": 5,
        },
    )
    assert response.status_code in (400, 422), response.text


@pytest.mark.asyncio
async def test_filing_with_a_function_but_no_cascade_level_is_refused(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    filing_category,
    filing_function,
    superuser_auth_headers: dict,
    test_session,
    monkeypatch,
):
    """NS-1: a PEL reference is banded by level, so it cannot be issued without one."""
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    asset = await _bound_evidence_asset(test_session, record_id=record["id"])
    _fake_storage(monkeypatch)

    response = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={
            "evidence_asset_id": asset.id,
            "category_id": filing_category.id,
            "function_code": filing_function.code,
        },
    )
    assert response.status_code == 422, response.text
    assert "cascade_level" in response.text

    # The refusal must not have half-filed the record.
    from src.domain.models.compliance_schedule import ComplianceRecord

    stored = await test_session.get(ComplianceRecord, record["id"])
    await test_session.refresh(stored)
    assert stored.library_document_id is None


@pytest.mark.asyncio
async def test_filing_evidence_from_a_different_occurrence_is_refused(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    filing_category,
    superuser_auth_headers: dict,
    test_session,
    monkeypatch,
):
    """The asset exists and is in-tenant; it is simply not this occurrence's."""
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    stranger = await _bound_evidence_asset(test_session, record_id=record["id"] + 9999)
    _fake_storage(monkeypatch)

    response = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={"evidence_asset_id": stranger.id, "category_id": filing_category.id},
    )
    assert response.status_code == 404, response.text

    reread = await client.get(
        f"/api/v1/compliance-schedule/records/{record['id']}",
        headers=superuser_auth_headers,
    )
    assert reread.json()["filing_status"] == "not_filed"


@pytest.mark.asyncio
async def test_a_failed_library_write_leaves_the_reason_on_the_occurrence(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    filing_category,
    superuser_auth_headers: dict,
    test_session,
    monkeypatch,
):
    """The point of ``filing_failed``: a filing that did not happen must say so."""
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    asset = await _bound_evidence_asset(test_session, record_id=record["id"])
    _fake_storage(monkeypatch, upload_error=StorageError("container missing"))

    response = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={"evidence_asset_id": asset.id, "category_id": filing_category.id},
    )
    assert response.status_code == 502, response.text

    reread = await client.get(
        f"/api/v1/compliance-schedule/records/{record['id']}",
        headers=superuser_auth_headers,
    )
    body = reread.json()
    assert body["filing_status"] == "filing_failed"
    assert "container missing" in body["filing_error"]
    assert body["library_document_id"] is None


@pytest.mark.asyncio
async def test_a_failed_filing_can_be_retried(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    filing_category,
    superuser_auth_headers: dict,
    test_session,
    monkeypatch,
):
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    asset = await _bound_evidence_asset(test_session, record_id=record["id"])

    _fake_storage(monkeypatch, upload_error=StorageError("transient"))
    failed = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={"evidence_asset_id": asset.id, "category_id": filing_category.id},
    )
    assert failed.status_code == 502

    _fake_storage(monkeypatch)
    retried = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={"evidence_asset_id": asset.id, "category_id": filing_category.id},
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["record"]["filing_status"] == "filed"
    # The stale reason must not linger next to a successful filing.
    assert retried.json()["record"]["filing_error"] is None


@pytest.mark.asyncio
async def test_a_rolled_back_filing_leaves_no_library_document(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    filing_category,
    superuser_auth_headers: dict,
    test_session,
    monkeypatch,
):
    """A document row whose bytes never landed would be a broken Library entry."""
    from sqlalchemy import func, select

    from src.domain.models.document import Document

    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    asset = await _bound_evidence_asset(test_session, record_id=record["id"])

    before = (await test_session.execute(select(func.count()).select_from(Document))).scalar()

    _fake_storage(monkeypatch, upload_error=StorageError("container missing"))
    response = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={"evidence_asset_id": asset.id, "category_id": filing_category.id},
    )
    assert response.status_code == 502

    after = (await test_session.execute(select(func.count()).select_from(Document))).scalar()
    assert after == before


@pytest.mark.asyncio
async def test_unreadable_evidence_is_reported_and_recorded(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    filing_category,
    superuser_auth_headers: dict,
    test_session,
    monkeypatch,
):
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    asset = await _bound_evidence_asset(test_session, record_id=record["id"])
    _fake_storage(monkeypatch, download=StorageError("blob 404"))

    response = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={"evidence_asset_id": asset.id, "category_id": filing_category.id},
    )
    assert response.status_code == 502, response.text

    reread = await client.get(
        f"/api/v1/compliance-schedule/records/{record['id']}",
        headers=superuser_auth_headers,
    )
    assert reread.json()["filing_status"] == "filing_failed"


@pytest.mark.asyncio
async def test_evidence_the_library_cannot_hold_is_rejected(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    filing_category,
    superuser_auth_headers: dict,
    test_session,
    monkeypatch,
):
    """Video is valid evidence and is not a Library file type. Say so, plainly."""
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    asset = await _bound_evidence_asset(test_session, record_id=record["id"], filename="walkaround.mp4")
    _fake_storage(monkeypatch)

    response = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers=superuser_auth_headers,
        json={"evidence_asset_id": asset.id, "category_id": filing_category.id},
    )
    assert response.status_code == 422, response.text

    reread = await client.get(
        f"/api/v1/compliance-schedule/records/{record['id']}",
        headers=superuser_auth_headers,
    )
    # A request the caller can correct is not a filing failure.
    assert reread.json()["filing_status"] == "not_filed"


@pytest.mark.asyncio
async def test_filing_a_record_from_another_tenant_is_not_found(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    superuser_auth_headers: dict,
    test_session,
):
    record = await _completed_record(client, superuser_auth_headers, unique_template.template_key)
    document = await _library_document(test_session)

    # Same record id, a caller in a different tenant.
    from tests.integration.conftest import _generate_test_jwt

    other_tenant = _generate_test_jwt(user_id="1", tenant_id=999, role="admin", is_superuser=False)
    response = await client.post(
        f"/api/v1/compliance-schedule/records/{record['id']}/file",
        headers={"Authorization": f"Bearer {other_tenant}"},
        json={"library_document_id": document.id},
    )
    assert response.status_code == 404, response.text


def test_filing_is_not_wired_into_completion():
    """A structural check that ADR-0020's separation cannot regress quietly.

    The completion service must not import or call the filing bridge; if it ever
    does, 'complete' starts implying 'filed' and the register loses the ability
    to show the difference.
    """
    import inspect

    from src.domain.services import compliance_schedule_service

    source = inspect.getsource(compliance_schedule_service)
    assert "compliance_schedule_filing_service" not in source
    assert "file_record_to_library" not in source
