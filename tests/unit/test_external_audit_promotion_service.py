"""Path-to-10 S1: promotion collaborator + import facade identity."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.domain.models.compliance_evidence import EvidenceLinkMethod
from src.domain.models.external_audit_import import ExternalAuditDraftStatus, ExternalAuditImportStatus
from src.domain.services.external_audit_import_service import ExternalAuditImportService, PromotionResult
from src.domain.services.external_audit_promotion_service import ExternalAuditPromotionService
from src.domain.services.external_audit_promotion_service import PromotionResult as DomainPromotionResult


def test_promotion_result_reexport_is_canonical() -> None:
    assert PromotionResult is DomainPromotionResult


def test_import_facade_wires_promotion_collaborator() -> None:
    db = SimpleNamespace()
    service = ExternalAuditImportService(db)
    assert isinstance(service.promotion_service, ExternalAuditPromotionService)
    assert service.promotion_service.host is service
    assert ExternalAuditImportService._scheme_home("planet_mark") == ExternalAuditPromotionService._scheme_home(
        "planet_mark"
    )


def test_promotion_summary_uses_materialization_risk_gate() -> None:
    service = ExternalAuditPromotionService(SimpleNamespace())
    findings = [
        SimpleNamespace(finding_type="nonconformity", severity="medium", mapped_standards_json=[]),
        SimpleNamespace(finding_type="nonconformity", severity="low", mapped_standards_json=[]),
        SimpleNamespace(finding_type="positive_practice", severity="critical", mapped_standards_json=[]),
        SimpleNamespace(finding_type="observation", severity="high", mapped_standards_json=[]),
    ]

    summary = service._build_promotion_summary(findings=findings)

    assert summary["risk_candidates"] == 1
    assert summary["action_candidates"] == 2


@pytest.mark.asyncio
async def test_import_facade_delegates_link_evidence() -> None:
    deleted_link = SimpleNamespace(
        deleted_at=object(),
        linked_by=None,
        confidence=None,
        title=None,
        notes=None,
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: deleted_link)),
        add=Mock(),
        flush=AsyncMock(),
    )
    service = ExternalAuditImportService(db)
    await service._link_evidence_for_finding(
        finding_id=7,
        clause_ids=["iso-9001-8.1"],
        tenant_id=1,
        user_id=2,
        note="note",
        confidence=0.5,
    )
    assert deleted_link.deleted_at is None
    assert deleted_link.linked_by == EvidenceLinkMethod.AUTO
    assert deleted_link.confidence == 0.5
    assert deleted_link.notes == "note"


@pytest.mark.asyncio
async def test_enqueue_promote_returns_durable_promoting_job() -> None:
    review_job = SimpleNamespace(id=7, tenant_id=3, status=ExternalAuditImportStatus.REVIEW_REQUIRED)
    promoting_job = SimpleNamespace(id=7, tenant_id=3, status=ExternalAuditImportStatus.PROMOTING)
    accepted = SimpleNamespace(status=ExternalAuditDraftStatus.ACCEPTED)
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(rowcount=1)),
        commit=AsyncMock(),
    )
    host = SimpleNamespace(
        db=db,
        get_job=AsyncMock(side_effect=[review_job, promoting_job]),
        list_job_drafts=AsyncMock(return_value=[accepted]),
    )

    job = await ExternalAuditPromotionService(host).enqueue_promote(job_id=7, tenant_id=3, user_id=9)

    assert job.status == ExternalAuditImportStatus.PROMOTING
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_existing_registry_record_still_backfills_uvdb() -> None:
    existing_record = SimpleNamespace(
        id=11,
        carbon_reporting_year_id=None,
        scope_1_co2e=None,
        scope_2_co2e=None,
        scope_3_co2e=None,
    )
    uvdb_row = SimpleNamespace(id=22)
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one_or_none=lambda: existing_record),
                SimpleNamespace(scalar_one_or_none=lambda: uvdb_row),
            ]
        ),
        flush=AsyncMock(),
    )
    service = ExternalAuditPromotionService(SimpleNamespace(db=db))
    job = SimpleNamespace(
        id=7,
        detected_scheme="achilles_uvdb",
        provenance_json={},
        scheme_version=None,
        issuer_name=None,
        report_date=None,
        overall_score=None,
        max_score=None,
        score_percentage=None,
        score_breakdown_json=[],
        outcome_status=None,
        analysis_summary=None,
    )
    run = SimpleNamespace(
        reference_number="AUD-7",
        assurance_scheme="Achilles UVDB",
        title="Imported run",
        location=None,
        external_reference=None,
        external_body_name=None,
        external_auditor_name=None,
    )

    result = await service._sync_scheme_records(job=job, run=run, tenant_id=3, drafts=[])

    assert result["status"] == "already_synced"
    assert result["uvdb_audit_id"] == 22
    assert db.execute.await_count == 2
