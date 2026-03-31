"""Integration coverage for external audit OCR/import endpoints."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes import external_audit_imports
from src.domain.exceptions import ValidationError
from src.domain.models.audit import AuditFinding, AuditRun, AuditStatus, AuditTemplate, FindingStatus
from src.domain.models.evidence_asset import (
    EvidenceAsset,
    EvidenceAssetType,
    EvidenceRetentionPolicy,
    EvidenceSourceModule,
    EvidenceVisibility,
)
from src.domain.models.external_audit_import import (
    ExternalAuditDraft,
    ExternalAuditDraftStatus,
    ExternalAuditImportStatus,
)
from src.domain.services.external_audit_import_service import ExternalAuditImportService
from tests.conftest import generate_test_reference

DEFAULT_TEST_USER_ID = 1
DEFAULT_TEST_TENANT_ID = 1
pytestmark = pytest.mark.sqlite_minimal_schema


@pytest.mark.asyncio
async def test_external_audit_import_job_creation_queue_and_drafts(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = AuditTemplate(
        name="External Audit Intake",
        category="Compliance",
        audit_type="audit",
        created_by_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("TPL"),
        is_published=True,
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    run = AuditRun(
        template_id=template.id,
        title="Achilles import run",
        status=AuditStatus.SCHEDULED,
        created_by_id=DEFAULT_TEST_USER_ID,
        assigned_to_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        assurance_scheme="Achilles UVDB",
        reference_number=generate_test_reference("AUD"),
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)

    asset = EvidenceAsset(
        tenant_id=DEFAULT_TEST_TENANT_ID,
        storage_key="evidence/audit/test/achilles.md",
        original_filename="achilles.md",
        content_type="text/markdown",
        file_size_bytes=128,
        checksum_sha256="abc123",
        asset_type=EvidenceAssetType.DOCUMENT,
        source_module=EvidenceSourceModule.AUDIT,
        source_id=str(run.id),
        visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
        retention_policy=EvidenceRetentionPolicy.STANDARD,
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add(asset)
    await test_session.commit()
    await test_session.refresh(asset)

    run.source_document_asset_id = asset.id
    await test_session.commit()

    create_response = await client.post(
        "/api/v1/external-audit-imports/jobs",
        json={"audit_run_id": run.id, "source_document_asset_id": asset.id},
        headers=auth_headers,
    )

    assert create_response.status_code == 201
    job_id = create_response.json()["id"]

    monkeypatch.setattr(external_audit_imports.process_external_audit_import_job, "delay", lambda *_args: None)

    queue_response = await client.post(
        f"/api/v1/external-audit-imports/jobs/{job_id}/queue",
        headers=auth_headers,
    )
    assert queue_response.status_code == 200
    assert queue_response.json()["status"] == "queued"

    import src.domain.services.external_audit_import_service as import_service_module

    monkeypatch.setattr(
        import_service_module,
        "storage_service",
        lambda: SimpleNamespace(
            download=AsyncMock(
                return_value=(
                    b"Achilles audit report. Major non-conformance identified. "
                    b"Mapped to ISO 9001 and ISO 45001 requirements."
                )
            )
        ),
    )

    service = ExternalAuditImportService(test_session)
    await service.process_job(
        job_id=job_id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        user_id=DEFAULT_TEST_USER_ID,
    )
    await test_session.commit()

    job_response = await client.get(
        f"/api/v1/external-audit-imports/jobs/{job_id}",
        headers=auth_headers,
    )
    assert job_response.status_code == 200
    job_payload = job_response.json()
    assert job_payload["detected_scheme"] == "achilles_uvdb"
    assert job_payload["detected_scheme_confidence"] > 0.5
    assert job_payload["issuer_name"] == "Achilles"
    assert job_payload["provenance_json"]["processing_template_id"] == template.id
    assert job_payload["provenance_json"]["processing_template_version"] == run.template_version
    assert job_payload["provenance_json"]["declared_assurance_scheme"] == "Achilles UVDB"
    assert job_payload["provenance_json"]["declared_vs_detected"]["detected_scheme"] == "achilles_uvdb"
    assert job_payload["nonconformity_summary_json"]
    assert job_payload["promotion_summary_json"]["action_candidates"] >= 1
    assert job_payload["evidence_preview_json"]

    drafts_response = await client.get(
        f"/api/v1/external-audit-imports/jobs/{job_id}/drafts",
        headers=auth_headers,
    )
    assert drafts_response.status_code == 200
    drafts = drafts_response.json()
    assert len(drafts) >= 1
    draft = drafts[0]
    assert draft["status"] == "draft"
    assert draft["confidence_score"] > 0
    assert "Achilles UVDB" in {mapping["framework"] for mapping in draft["mapped_frameworks_json"]}
    assert {mapping["standard"] for mapping in draft["mapped_standards_json"]} >= {"ISO 9001", "ISO 45001"}

    review_response = await client.patch(
        f"/api/v1/external-audit-imports/drafts/{draft['id']}",
        json={"status": "accepted", "review_notes": "Validated by reviewer"},
        headers=auth_headers,
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_external_audit_import_job_is_idempotent(
    test_session: AsyncSession,
) -> None:
    template = AuditTemplate(
        name="External Audit Intake",
        category="Compliance",
        audit_type="audit",
        created_by_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("TPL"),
        is_published=True,
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    run = AuditRun(
        template_id=template.id,
        title="Idempotent import run",
        status=AuditStatus.SCHEDULED,
        created_by_id=DEFAULT_TEST_USER_ID,
        assigned_to_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("AUD"),
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)

    asset = EvidenceAsset(
        tenant_id=DEFAULT_TEST_TENANT_ID,
        storage_key="evidence/audit/test/idempotent.pdf",
        original_filename="idempotent.pdf",
        content_type="application/pdf",
        file_size_bytes=2048,
        checksum_sha256="sha256-fixed",
        asset_type=EvidenceAssetType.PDF,
        source_module=EvidenceSourceModule.AUDIT,
        source_id=str(run.id),
        visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
        retention_policy=EvidenceRetentionPolicy.STANDARD,
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add(asset)
    await test_session.commit()
    await test_session.refresh(asset)

    run.source_document_asset_id = asset.id
    await test_session.commit()

    service = ExternalAuditImportService(test_session)
    job_one = await service.create_job(
        audit_run_id=run.id,
        source_document_asset_id=asset.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        user_id=DEFAULT_TEST_USER_ID,
    )
    await test_session.commit()

    job_two = await service.create_job(
        audit_run_id=run.id,
        source_document_asset_id=asset.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        user_id=DEFAULT_TEST_USER_ID,
    )

    assert job_one.id == job_two.id
    assert job_one.idempotency_key == job_two.idempotency_key


@pytest.mark.asyncio
async def test_external_audit_import_job_queue_is_idempotent(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = AuditTemplate(
        name="External Audit Intake",
        category="Compliance",
        audit_type="audit",
        created_by_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("TPL"),
        is_published=True,
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    run = AuditRun(
        template_id=template.id,
        title="Queue-safe import run",
        status=AuditStatus.SCHEDULED,
        created_by_id=DEFAULT_TEST_USER_ID,
        assigned_to_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("AUD"),
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)

    asset = EvidenceAsset(
        tenant_id=DEFAULT_TEST_TENANT_ID,
        storage_key="evidence/audit/test/queue-safe.pdf",
        original_filename="queue-safe.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        checksum_sha256="queue-safe-sha",
        asset_type=EvidenceAssetType.PDF,
        source_module=EvidenceSourceModule.AUDIT,
        source_id=str(run.id),
        visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
        retention_policy=EvidenceRetentionPolicy.STANDARD,
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add(asset)
    await test_session.commit()
    await test_session.refresh(asset)

    run.source_document_asset_id = asset.id
    await test_session.commit()

    create_response = await client.post(
        "/api/v1/external-audit-imports/jobs",
        json={"audit_run_id": run.id, "source_document_asset_id": asset.id},
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["id"]

    delay_calls: list[tuple[int, int, int]] = []

    def _delay(job_id_value: int, tenant_id_value: int, user_id_value: int) -> None:
        delay_calls.append((job_id_value, tenant_id_value, user_id_value))

    monkeypatch.setattr(external_audit_imports.process_external_audit_import_job, "delay", _delay)

    first_queue = await client.post(
        f"/api/v1/external-audit-imports/jobs/{job_id}/queue",
        headers=auth_headers,
    )
    second_queue = await client.post(
        f"/api/v1/external-audit-imports/jobs/{job_id}/queue",
        headers=auth_headers,
    )

    assert first_queue.status_code == 200
    assert second_queue.status_code == 200
    assert first_queue.json()["status"] == "queued"
    assert second_queue.json()["status"] == "queued"
    assert delay_calls == [(job_id, DEFAULT_TEST_TENANT_ID, DEFAULT_TEST_USER_ID)]


@pytest.mark.asyncio
async def test_external_audit_import_queue_failure_keeps_job_retryable(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = AuditTemplate(
        name="External Audit Intake",
        category="Compliance",
        audit_type="audit",
        created_by_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("TPL"),
        is_published=True,
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    run = AuditRun(
        template_id=template.id,
        title="Retryable import run",
        status=AuditStatus.SCHEDULED,
        created_by_id=DEFAULT_TEST_USER_ID,
        assigned_to_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("AUD"),
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)

    asset = EvidenceAsset(
        tenant_id=DEFAULT_TEST_TENANT_ID,
        storage_key="evidence/audit/test/retryable.pdf",
        original_filename="retryable.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        checksum_sha256="retryable-queue-sha",
        asset_type=EvidenceAssetType.PDF,
        source_module=EvidenceSourceModule.AUDIT,
        source_id=str(run.id),
        visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
        retention_policy=EvidenceRetentionPolicy.STANDARD,
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add(asset)
    await test_session.commit()
    await test_session.refresh(asset)

    run.source_document_asset_id = asset.id
    await test_session.commit()

    create_response = await client.post(
        "/api/v1/external-audit-imports/jobs",
        json={"audit_run_id": run.id, "source_document_asset_id": asset.id},
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["id"]

    monkeypatch.setattr(
        external_audit_imports.process_external_audit_import_job,
        "delay",
        lambda *_args: (_ for _ in ()).throw(ValueError("broker misconfigured")),
    )

    failed_queue = await client.post(
        f"/api/v1/external-audit-imports/jobs/{job_id}/queue",
        headers=auth_headers,
    )
    assert failed_queue.status_code == 502

    job_after_failure = await client.get(
        f"/api/v1/external-audit-imports/jobs/{job_id}",
        headers=auth_headers,
    )
    assert job_after_failure.status_code == 200
    assert job_after_failure.json()["status"] == "pending"
    assert job_after_failure.json()["error_code"] == "QUEUE_DISPATCH_FAILED"

    delay_calls: list[tuple[int, int, int]] = []

    def _delay(job_id_value: int, tenant_id_value: int, user_id_value: int) -> None:
        delay_calls.append((job_id_value, tenant_id_value, user_id_value))

    monkeypatch.setattr(external_audit_imports.process_external_audit_import_job, "delay", _delay)

    retried_queue = await client.post(
        f"/api/v1/external-audit-imports/jobs/{job_id}/queue",
        headers=auth_headers,
    )
    assert retried_queue.status_code == 200
    assert retried_queue.json()["status"] == "queued"
    assert delay_calls == [(job_id, DEFAULT_TEST_TENANT_ID, DEFAULT_TEST_USER_ID)]


@pytest.mark.asyncio
async def test_external_audit_import_latest_job_for_run_returns_most_recent_job(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict,
) -> None:
    template = AuditTemplate(
        name="External Audit Intake",
        category="Compliance",
        audit_type="audit",
        created_by_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("TPL"),
        is_published=True,
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    run = AuditRun(
        template_id=template.id,
        title="Latest-job import run",
        status=AuditStatus.SCHEDULED,
        created_by_id=DEFAULT_TEST_USER_ID,
        assigned_to_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("AUD"),
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)

    asset_one = EvidenceAsset(
        tenant_id=DEFAULT_TEST_TENANT_ID,
        storage_key="evidence/audit/test/latest-one.pdf",
        original_filename="latest-one.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        checksum_sha256="latest-one-sha",
        asset_type=EvidenceAssetType.PDF,
        source_module=EvidenceSourceModule.AUDIT,
        source_id=str(run.id),
        visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
        retention_policy=EvidenceRetentionPolicy.STANDARD,
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    asset_two = EvidenceAsset(
        tenant_id=DEFAULT_TEST_TENANT_ID,
        storage_key="evidence/audit/test/latest-two.pdf",
        original_filename="latest-two.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        checksum_sha256="latest-two-sha",
        asset_type=EvidenceAssetType.PDF,
        source_module=EvidenceSourceModule.AUDIT,
        source_id=str(run.id),
        visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
        retention_policy=EvidenceRetentionPolicy.STANDARD,
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add_all([asset_one, asset_two])
    await test_session.commit()
    await test_session.refresh(asset_one)
    await test_session.refresh(asset_two)

    create_response_one = await client.post(
        "/api/v1/external-audit-imports/jobs",
        json={"audit_run_id": run.id, "source_document_asset_id": asset_one.id},
        headers=auth_headers,
    )
    create_response_two = await client.post(
        "/api/v1/external-audit-imports/jobs",
        json={"audit_run_id": run.id, "source_document_asset_id": asset_two.id},
        headers=auth_headers,
    )

    assert create_response_one.status_code == 201
    assert create_response_two.status_code == 201

    latest_job_response = await client.get(
        f"/api/v1/external-audit-imports/runs/{run.id}/latest-job",
        headers=auth_headers,
    )
    assert latest_job_response.status_code == 200
    assert latest_job_response.json()["id"] == create_response_two.json()["id"]
    assert latest_job_response.json()["source_document_asset_id"] == asset_two.id


@pytest.mark.asyncio
async def test_process_job_failure_preserves_existing_drafts(
    test_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = AuditTemplate(
        name="External Audit Intake",
        category="Compliance",
        audit_type="audit",
        created_by_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("TPL"),
        is_published=True,
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    run = AuditRun(
        template_id=template.id,
        title="Failure-safe import run",
        status=AuditStatus.SCHEDULED,
        created_by_id=DEFAULT_TEST_USER_ID,
        assigned_to_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        assurance_scheme="Achilles UVDB",
        reference_number=generate_test_reference("AUD"),
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)

    asset = EvidenceAsset(
        tenant_id=DEFAULT_TEST_TENANT_ID,
        storage_key="evidence/audit/test/failure-safe.md",
        original_filename="failure-safe.md",
        content_type="text/markdown",
        file_size_bytes=256,
        checksum_sha256="failure-safe-sha",
        asset_type=EvidenceAssetType.DOCUMENT,
        source_module=EvidenceSourceModule.AUDIT,
        source_id=str(run.id),
        visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
        retention_policy=EvidenceRetentionPolicy.STANDARD,
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add(asset)
    await test_session.commit()
    await test_session.refresh(asset)

    run.source_document_asset_id = asset.id
    await test_session.commit()

    service = ExternalAuditImportService(test_session)
    job = await service.create_job(
        audit_run_id=run.id,
        source_document_asset_id=asset.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        user_id=DEFAULT_TEST_USER_ID,
    )
    job.status = ExternalAuditImportStatus.QUEUED
    await test_session.flush()

    test_session.add(
        ExternalAuditDraft(
            import_job_id=job.id,
            audit_run_id=run.id,
            tenant_id=DEFAULT_TEST_TENANT_ID,
            status=ExternalAuditDraftStatus.DRAFT,
            title="Preserve me",
            description="Existing reviewer work",
            severity="medium",
            finding_type="nonconformity",
            created_by_id=DEFAULT_TEST_USER_ID,
            updated_by_id=DEFAULT_TEST_USER_ID,
        )
    )
    await test_session.commit()

    import src.domain.services.external_audit_import_service as import_service_module

    monkeypatch.setattr(
        import_service_module,
        "storage_service",
        lambda: SimpleNamespace(download=AsyncMock(return_value=b"Achilles import content")),
    )
    monkeypatch.setattr(
        service.analysis_service, "analyze", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    processed_job = await service.process_job(
        job_id=job.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        user_id=DEFAULT_TEST_USER_ID,
    )
    await test_session.commit()

    drafts = await service.list_job_drafts(job_id=job.id, tenant_id=DEFAULT_TEST_TENANT_ID)
    assert processed_job.status == ExternalAuditImportStatus.FAILED
    assert len(drafts) == 1
    assert drafts[0].title == "Preserve me"


@pytest.mark.asyncio
async def test_process_job_is_noop_once_review_is_ready(
    test_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = AuditTemplate(
        name="External Audit Intake",
        category="Compliance",
        audit_type="audit",
        created_by_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("TPL"),
        is_published=True,
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    run = AuditRun(
        template_id=template.id,
        title="Ready-for-review import run",
        status=AuditStatus.SCHEDULED,
        created_by_id=DEFAULT_TEST_USER_ID,
        assigned_to_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("AUD"),
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)

    asset = EvidenceAsset(
        tenant_id=DEFAULT_TEST_TENANT_ID,
        storage_key="evidence/audit/test/review-ready.pdf",
        original_filename="review-ready.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        checksum_sha256="review-ready-sha",
        asset_type=EvidenceAssetType.PDF,
        source_module=EvidenceSourceModule.AUDIT,
        source_id=str(run.id),
        visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
        retention_policy=EvidenceRetentionPolicy.STANDARD,
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add(asset)
    await test_session.commit()
    await test_session.refresh(asset)

    service = ExternalAuditImportService(test_session)
    job = await service.create_job(
        audit_run_id=run.id,
        source_document_asset_id=asset.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        user_id=DEFAULT_TEST_USER_ID,
    )
    job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
    await test_session.flush()

    test_session.add(
        ExternalAuditDraft(
            import_job_id=job.id,
            audit_run_id=run.id,
            tenant_id=DEFAULT_TEST_TENANT_ID,
            status=ExternalAuditDraftStatus.DRAFT,
            title="Keep reviewer work",
            description="Existing draft should survive duplicate delivery",
            severity="medium",
            finding_type="nonconformity",
            created_by_id=DEFAULT_TEST_USER_ID,
            updated_by_id=DEFAULT_TEST_USER_ID,
        )
    )
    await test_session.commit()

    download_mock = AsyncMock(return_value=b"should-not-run")
    import src.domain.services.external_audit_import_service as import_service_module

    monkeypatch.setattr(
        import_service_module,
        "storage_service",
        lambda: SimpleNamespace(download=download_mock),
    )

    processed_job = await service.process_job(
        job_id=job.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        user_id=DEFAULT_TEST_USER_ID,
    )
    await test_session.commit()

    drafts = await service.list_job_drafts(job_id=job.id, tenant_id=DEFAULT_TEST_TENANT_ID)
    assert processed_job.status == ExternalAuditImportStatus.REVIEW_REQUIRED
    assert len(drafts) == 1
    assert drafts[0].title == "Keep reviewer work"
    download_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_promote_requires_review_required_and_completes_external_audit_outcome(
    test_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = AuditTemplate(
        name="External Audit Intake",
        category="Compliance",
        audit_type="audit",
        created_by_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("TPL"),
        is_published=True,
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    run = AuditRun(
        template_id=template.id,
        title="Promotion-safe import run",
        status=AuditStatus.SCHEDULED,
        created_by_id=DEFAULT_TEST_USER_ID,
        assigned_to_id=DEFAULT_TEST_USER_ID,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        reference_number=generate_test_reference("AUD"),
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)

    asset = EvidenceAsset(
        tenant_id=DEFAULT_TEST_TENANT_ID,
        storage_key="evidence/audit/test/promotion-safe.pdf",
        original_filename="promotion-safe.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        checksum_sha256="promotion-safe-sha",
        asset_type=EvidenceAssetType.PDF,
        source_module=EvidenceSourceModule.AUDIT,
        source_id=str(run.id),
        visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
        retention_policy=EvidenceRetentionPolicy.STANDARD,
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add(asset)
    await test_session.commit()
    await test_session.refresh(asset)

    run.source_document_asset_id = asset.id
    await test_session.commit()

    service = ExternalAuditImportService(test_session)
    job = await service.create_job(
        audit_run_id=run.id,
        source_document_asset_id=asset.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        user_id=DEFAULT_TEST_USER_ID,
    )
    job.status = ExternalAuditImportStatus.PROCESSING
    await test_session.flush()

    accepted_draft = ExternalAuditDraft(
        import_job_id=job.id,
        audit_run_id=run.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        status=ExternalAuditDraftStatus.ACCEPTED,
        title="Promote me",
        description="Imported nonconformity",
        severity="high",
        finding_type="nonconformity",
        mapped_standards_json=[{"clause_id": "iso-9001-8.1", "standard": "ISO 9001", "clause_number": "8.1"}],
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add(accepted_draft)
    await test_session.commit()

    with pytest.raises(ValidationError):
        await service.promote_job(job_id=job.id, tenant_id=DEFAULT_TEST_TENANT_ID, user_id=DEFAULT_TEST_USER_ID)

    job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
    job.score_percentage = 91.5
    job.overall_score = 91.5
    job.max_score = 100
    job.outcome_status = "pass"
    await test_session.commit()

    async def _create_persisted_finding(*_args, **_kwargs) -> AuditFinding:
        finding = AuditFinding(
            run_id=run.id,
            title=accepted_draft.title,
            description=accepted_draft.description,
            severity=accepted_draft.severity,
            finding_type=accepted_draft.finding_type,
            status=FindingStatus.OPEN,
            corrective_action_required=True,
            reference_number=generate_test_reference("FND"),
            created_by_id=DEFAULT_TEST_USER_ID,
            tenant_id=DEFAULT_TEST_TENANT_ID,
        )
        test_session.add(finding)
        await test_session.flush()
        return finding

    monkeypatch.setattr(
        "src.domain.services.audit_service.AuditService.create_finding",
        _create_persisted_finding,
    )
    monkeypatch.setattr(service, "_link_evidence_for_finding", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_link_source_document_evidence", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_sync_scheme_records", AsyncMock(return_value={"status": "not_synced"}))

    promoted_job = await service.promote_job(
        job_id=job.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        user_id=DEFAULT_TEST_USER_ID,
    )
    await test_session.commit()
    await test_session.refresh(run)

    assert promoted_job.status == ExternalAuditImportStatus.COMPLETED
    assert run.status == AuditStatus.COMPLETED
    assert run.completed_at is not None
    assert run.score == 91.5
    assert run.max_score == 100
    assert run.score_percentage == 91.5
    assert run.passed is True
