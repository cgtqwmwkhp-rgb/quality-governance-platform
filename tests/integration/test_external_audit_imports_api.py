"""Integration coverage for external audit OCR/import endpoints."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes import external_audit_imports
from src.domain.models.audit import AuditRun, AuditTemplate, AuditStatus
from src.domain.models.evidence_asset import (
    EvidenceAsset,
    EvidenceAssetType,
    EvidenceRetentionPolicy,
    EvidenceSourceModule,
    EvidenceVisibility,
)
from src.domain.services.external_audit_import_service import ExternalAuditImportService
from tests.conftest import generate_test_reference


@pytest.mark.asyncio
async def test_external_audit_import_job_creation_queue_and_drafts(
    client: AsyncClient,
    test_session: AsyncSession,
    test_user,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = AuditTemplate(
        name="External Audit Intake",
        category="Compliance",
        audit_type="audit",
        created_by_id=test_user.id,
        tenant_id=test_user.tenant_id,
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
        created_by_id=test_user.id,
        assigned_to_id=test_user.id,
        tenant_id=test_user.tenant_id,
        assurance_scheme="Achilles UVDB",
        reference_number=generate_test_reference("AUD"),
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)

    asset = EvidenceAsset(
        tenant_id=test_user.tenant_id,
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
        created_by_id=test_user.id,
        updated_by_id=test_user.id,
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
    await service.process_job(job_id=job_id, tenant_id=test_user.tenant_id, user_id=test_user.id)
    await test_session.commit()

    drafts_response = await client.get(
        f"/api/v1/external-audit-imports/jobs/{job_id}/drafts",
        headers=auth_headers,
    )
    assert drafts_response.status_code == 200
    drafts = drafts_response.json()
    assert len(drafts) >= 1
    assert drafts[0]["title"].startswith("Achilles UVDB")
    assert drafts[0]["mapped_frameworks_json"][0]["framework"] == "Achilles UVDB"
    assert {mapping["standard"] for mapping in drafts[0]["mapped_standards_json"]} >= {"ISO 9001", "ISO 45001"}

    review_response = await client.patch(
        f"/api/v1/external-audit-imports/drafts/{drafts[0]['id']}",
        json={"status": "accepted", "review_notes": "Validated by reviewer"},
        headers=auth_headers,
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_external_audit_import_job_is_idempotent(
    test_session: AsyncSession,
    test_user,
) -> None:
    template = AuditTemplate(
        name="External Audit Intake",
        category="Compliance",
        audit_type="audit",
        created_by_id=test_user.id,
        tenant_id=test_user.tenant_id,
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
        created_by_id=test_user.id,
        assigned_to_id=test_user.id,
        tenant_id=test_user.tenant_id,
        reference_number=generate_test_reference("AUD"),
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)

    asset = EvidenceAsset(
        tenant_id=test_user.tenant_id,
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
        created_by_id=test_user.id,
        updated_by_id=test_user.id,
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
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
    )
    await test_session.commit()

    job_two = await service.create_job(
        audit_run_id=run.id,
        source_document_asset_id=asset.id,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
    )

    assert job_one.id == job_two.id
    assert job_one.idempotency_key == job_two.idempotency_key
