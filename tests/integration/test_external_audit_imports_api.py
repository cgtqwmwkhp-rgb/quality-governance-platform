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

    process_response = await client.post(
        f"/api/v1/external-audit-imports/jobs/{job_id}/process",
        headers=auth_headers,
    )
    assert process_response.status_code == 200
    assert process_response.json()["status"] == "review_required"

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
async def test_external_audit_bulk_review_accepts_all_pending_drafts(
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
        title="Bulk review import run",
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
        storage_key="evidence/audit/test/bulk-review.pdf",
        original_filename="bulk-review.pdf",
        content_type="application/pdf",
        file_size_bytes=256,
        checksum_sha256="bulk-review-asset",
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

    from src.domain.models.external_audit_import import ExternalAuditImportJob

    import_job = ExternalAuditImportJob(
        reference_number=generate_test_reference("IMP"),
        audit_run_id=run.id,
        source_document_asset_id=asset.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        status=ExternalAuditImportStatus.REVIEW_REQUIRED,
        source_checksum_sha256="bulk-review",
        idempotency_key=f"{run.id}:bulk-review",
        source_filename="bulk.pdf",
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add(import_job)
    await test_session.commit()
    await test_session.refresh(import_job)

    draft_one = ExternalAuditDraft(
        import_job_id=import_job.id,
        audit_run_id=run.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        status=ExternalAuditDraftStatus.DRAFT,
        title="First draft",
        description="First draft evidence",
        severity="high",
        finding_type="nonconformity",
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    draft_two = ExternalAuditDraft(
        import_job_id=import_job.id,
        audit_run_id=run.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        status=ExternalAuditDraftStatus.DRAFT,
        title="Second draft",
        description="Second draft evidence",
        severity="medium",
        finding_type="question_answered_no",
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add_all([draft_one, draft_two])
    await test_session.commit()

    response = await client.post(
        f"/api/v1/external-audit-imports/jobs/{import_job.id}/bulk-review",
        json={"status": "accepted"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert {draft["status"] for draft in payload} == {"accepted"}


@pytest.mark.asyncio
async def test_external_audit_import_reconciliation_endpoint_returns_downstream_contract(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {
        "job_id": 72,
        "audit_run_id": 41,
        "audit_reference": "AUD-00041",
        "job_status": "completed",
        "canonical_read_model": "specialist_sync_verification",
        "specialist_home": {"path": "/uvdb", "label": "Achilles / UVDB"},
        "scheme_alignment": {"uvdb_audit_id": 18},
        "accepted_total": 1,
        "promoted_total": 1,
        "accepted_pending_total": 0,
        "failed_total": 0,
        "failed_drafts": [],
        "materialized": {
            "audit_findings": 1,
            "capa_actions": 1,
            "enterprise_risks": 1,
            "uvdb_audit_id": 18,
            "external_audit_record_id": 22,
        },
        "proof_matrix": [
            {"step": "upload", "status": "ok", "detail": "report.pdf"},
            {"step": "promotion", "status": "ok", "detail": "1 finding(s) materialized"},
        ],
        "draft_results": [
            {
                "draft_id": 9,
                "draft_title": "NC",
                "draft_status": "promoted",
                "finding_type": "nonconformity",
                "severity": "high",
                "finding_id": 100,
                "finding_reference": "FND-2026-0001",
                "capa_actions": [{"id": 5, "reference_number": "CAPA-2026-0001", "title": "Action plan"}],
                "enterprise_risks": [{"id": 7, "reference": "RSK-2026-0001", "title": "Audit escalation"}],
                "view_links": {
                    "actions": "/actions?sourceType=audit_finding&sourceId=100",
                    "risk_register": "/risk-register?auditOnly=1&auditRef=AUD-00041",
                    "uvdb": "/uvdb?auditRef=AUD-00041",
                },
            }
        ],
        "view_links": {
            "actions": "/actions?sourceType=audit_finding",
            "risk_register": "/risk-register?auditOnly=1&auditRef=AUD-00041",
            "uvdb": "/uvdb?auditRef=AUD-00041",
            "specialist_home": "/uvdb?auditRef=AUD-00041",
        },
    }
    monkeypatch.setattr(
        ExternalAuditImportService,
        "get_promotion_reconciliation",
        AsyncMock(return_value=expected),
    )

    response = await client.get(
        "/api/v1/external-audit-imports/jobs/72/reconciliation",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["canonical_read_model"] == "specialist_sync_verification"
    assert payload["materialized"]["capa_actions"] == 1
    assert payload["view_links"]["actions"] == "/actions?sourceType=audit_finding"


@pytest.mark.asyncio
async def test_external_audit_service_recovers_tenanted_jobs_when_request_has_no_tenant(
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
        title="Tenant fallback import run",
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
        storage_key="evidence/audit/test/tenant-fallback.pdf",
        original_filename="tenant-fallback.pdf",
        content_type="application/pdf",
        file_size_bytes=256,
        checksum_sha256="tenant-fallback-asset",
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

    from src.domain.models.external_audit_import import ExternalAuditImportJob

    job = ExternalAuditImportJob(
        reference_number=generate_test_reference("IMP"),
        audit_run_id=run.id,
        source_document_asset_id=asset.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        status=ExternalAuditImportStatus.REVIEW_REQUIRED,
        source_checksum_sha256="tenant-fallback",
        idempotency_key=f"{run.id}:tenant-fallback",
        source_filename="tenant-fallback.pdf",
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    draft = ExternalAuditDraft(
        import_job_id=0,
        audit_run_id=run.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        status=ExternalAuditDraftStatus.DRAFT,
        title="Fallback draft",
        description="Fallback evidence",
        severity="medium",
        finding_type="nonconformity",
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add(job)
    await test_session.commit()
    await test_session.refresh(job)
    draft.import_job_id = job.id
    test_session.add(draft)
    await test_session.commit()

    service = ExternalAuditImportService(test_session)

    recovered_job = await service.get_job(job_id=job.id, tenant_id=None)
    recovered_drafts = await service.list_job_drafts(job_id=job.id, tenant_id=None)

    assert recovered_job.id == job.id
    assert recovered_job.tenant_id == DEFAULT_TEST_TENANT_ID
    assert len(recovered_drafts) == 1
    assert recovered_drafts[0].id == draft.id


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

    fallback_queue = await client.post(
        f"/api/v1/external-audit-imports/jobs/{job_id}/queue",
        headers=auth_headers,
    )
    assert fallback_queue.status_code == 200
    assert fallback_queue.json()["status"] == "queued"


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


@pytest.mark.asyncio
async def test_external_audit_partial_promotion_stays_recoverable(
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
        title="Recoverable promotion run",
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
        storage_key="evidence/audit/test/partial.pdf",
        original_filename="partial.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        checksum_sha256="partial-promotion-sha",
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
    job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
    job.score_percentage = 88
    job.overall_score = 88
    job.max_score = 100
    job.outcome_status = "pass"
    await test_session.flush()

    good_draft = ExternalAuditDraft(
        import_job_id=job.id,
        audit_run_id=run.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        status=ExternalAuditDraftStatus.ACCEPTED,
        title="Promote me",
        description="Imported nonconformity",
        severity="high",
        finding_type="nonconformity",
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    bad_draft = ExternalAuditDraft(
        import_job_id=job.id,
        audit_run_id=run.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        status=ExternalAuditDraftStatus.ACCEPTED,
        title="Fail me",
        description="Imported issue that should fail",
        severity="medium",
        finding_type="question_answered_no",
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add_all([good_draft, bad_draft])
    await test_session.commit()

    async def _create_partially(_self, run_id: int, finding_data: dict, **_kwargs) -> AuditFinding:
        if finding_data["title"] == "Fail me":
            raise RuntimeError("simulated downstream failure")
        finding = AuditFinding(
            run_id=run_id,
            title=finding_data["title"],
            description=finding_data["description"],
            severity=finding_data["severity"],
            finding_type=finding_data["finding_type"],
            status=FindingStatus.OPEN,
            corrective_action_required=True,
            reference_number=generate_test_reference("FND"),
            created_by_id=DEFAULT_TEST_USER_ID,
            tenant_id=DEFAULT_TEST_TENANT_ID,
        )
        test_session.add(finding)
        await test_session.flush()
        return finding

    monkeypatch.setattr("src.domain.services.audit_service.AuditService.create_finding", _create_partially)
    monkeypatch.setattr(service, "_link_evidence_for_finding", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_link_source_document_evidence", AsyncMock(return_value=None))
    monkeypatch.setattr(
        service,
        "_sync_scheme_records",
        AsyncMock(
            return_value={
                "status": "synced",
                "uvdb_audit_id": None,
                "external_audit_record_id": None,
                "home_route": "/uvdb",
                "home_label": "Achilles / UVDB",
            }
        ),
    )

    promoted_job = await service.promote_job(
        job_id=job.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        user_id=DEFAULT_TEST_USER_ID,
    )

    assert promoted_job.status == ExternalAuditImportStatus.REVIEW_REQUIRED
    assert promoted_job.promotion_summary_json is not None
    assert len(promoted_job.promotion_summary_json["failed_drafts"]) == 1
    reconciliation = promoted_job.promotion_summary_json["reconciliation"]
    assert reconciliation["failed_total"] == 1
    assert reconciliation["promoted_total"] == 1


@pytest.mark.asyncio
async def test_external_audit_all_accepted_drafts_fail_promote_raises_validation_error(
    test_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When every accepted draft fails materialization, surface 422-style ValidationError (not opaque 500)."""
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
        title="All-fail promotion run",
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
        storage_key="evidence/audit/test/allfail.pdf",
        original_filename="allfail.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        checksum_sha256="all-fail-promotion-sha",
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
    job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
    job.score_percentage = 88
    job.overall_score = 88
    job.max_score = 100
    job.outcome_status = "pass"
    await test_session.flush()

    only_bad = ExternalAuditDraft(
        import_job_id=job.id,
        audit_run_id=run.id,
        tenant_id=DEFAULT_TEST_TENANT_ID,
        status=ExternalAuditDraftStatus.ACCEPTED,
        title="Always fails",
        description="Imported issue that should fail",
        severity="medium",
        finding_type="question_answered_no",
        created_by_id=DEFAULT_TEST_USER_ID,
        updated_by_id=DEFAULT_TEST_USER_ID,
    )
    test_session.add(only_bad)
    await test_session.commit()

    async def _always_fail(_self, run_id: int, finding_data: dict, **_kwargs) -> AuditFinding:
        raise RuntimeError("simulated downstream failure for all drafts")

    monkeypatch.setattr("src.domain.services.audit_service.AuditService.create_finding", _always_fail)
    monkeypatch.setattr(service, "_link_evidence_for_finding", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_link_source_document_evidence", AsyncMock(return_value=None))

    with pytest.raises(ValidationError) as excinfo:
        await service.promote_job(
            job_id=job.id,
            tenant_id=DEFAULT_TEST_TENANT_ID,
            user_id=DEFAULT_TEST_USER_ID,
        )

    err = excinfo.value
    assert "accepted draft" in err.message.lower() or "materialize" in err.message.lower()
    assert err.details.get("failed_total") == 1
    assert isinstance(err.details.get("failed_drafts"), list)
    assert len(err.details["failed_drafts"]) == 1
