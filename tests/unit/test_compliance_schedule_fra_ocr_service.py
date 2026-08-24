"""Unit tests for Compliance Schedule FRA OCR draft service (mocked DB)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import ConflictError, ValidationError
from src.domain.models.compliance_schedule import ComplianceOcrDraftStatus, ComplianceOcrFilingStatus
from src.domain.services.compliance_schedule_fra_ocr_service import ComplianceScheduleFraOcrService
from src.domain.services.compliance_schedule_service import ComplianceScheduleService


def _fra_requirement(**overrides):
    base = {
        "id": 10,
        "tenant_id": 1,
        "reference_number": "CSR-2026-0001",
        "title": "Fire risk assessment — Site A",
        "location_id": 5,
        "taxonomy_id": "03.01",
        "template_id": 99,
        "is_active": True,
        "owner_id": 42,
        "next_due_date": date(2026, 3, 14),
        "updated_by_id": None,
        "template": SimpleNamespace(template_key=ComplianceScheduleService.FRA_TEMPLATE_KEY),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _pending_draft(**overrides):
    base = {
        "id": 7,
        "external_id": "draft-ext",
        "tenant_id": 1,
        "requirement_id": 10,
        "status": ComplianceOcrDraftStatus.PENDING,
        "filing_status": ComplianceOcrFilingStatus.NOT_FILED,
        "library_document_id": None,
        "extraction_method": "pdfplumber",
        "source_checksum_sha256": "abc",
        "source_storage_key": "compliance-schedule/fra-ocr/1/x/a.pdf",
        # None = upload-owned staging blob; set for from-evidence drafts.
        "evidence_asset_id": None,
        "proposed_json": {"actions": []},
        "warnings_json": [],
        "confirmed_json": None,
        "applied_json": None,
        "confirmed_at": None,
        "confirmed_by_id": None,
        "discarded_at": None,
        "updated_by_id": None,
        "filing_error": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _extraction(**overrides):
    base = {
        "extraction_method": "pdfplumber",
        "ocr_provider_status": "skipped",
        "page_count": 1,
        "warnings": [],
        "to_proposed_json": MagicMock(return_value={"actions": []}),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _evidence_asset(**overrides):
    import hashlib

    content = overrides.pop("content", b"%PDF-1.4 minimal")
    checksum = hashlib.sha256(content).hexdigest()
    base = {
        "id": 99,
        "storage_key": "evidence/compliance_record/55/fra.pdf",
        "checksum_sha256": checksum,
        "original_filename": "fra.pdf",
        "title": "FRA",
        "content_type": "application/pdf",
        "_content": content,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_apply_confirmed_plan_updates_next_due_date_only() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)

    requirement = _fra_requirement()
    draft = _pending_draft()

    async def _load_draft(**kwargs):
        return draft

    async def _load_req(**kwargs):
        return requirement

    service._load_draft = _load_draft  # type: ignore[method-assign]
    service._load_fra_requirement = _load_req  # type: ignore[method-assign]

    with patch(
        "src.domain.services.compliance_schedule_fra_ocr_service.record_audit_event",
        new_callable=AsyncMock,
    ) as audit:
        draft_out, req_out, summary = await service.apply_confirmed_plan(
            draft_id=7,
            tenant_id=1,
            user_id=42,
            next_due_date=date(2027, 3, 14),
            actions=[],
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

    assert req_out.next_due_date == date(2027, 3, 14)
    assert draft_out.status == ComplianceOcrDraftStatus.CONFIRMED
    assert summary["actions_created"] == 0
    assert summary["actions_recorded"] == 0
    assert summary["changed_fields"] == ["next_due_date"]
    assert audit.await_count == 2


@pytest.mark.asyncio
async def test_apply_confirmed_plan_refuses_non_pending() -> None:
    db = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    draft = _pending_draft(status=ComplianceOcrDraftStatus.CONFIRMED)

    async def _load_draft(**kwargs):
        return draft

    service._load_draft = _load_draft  # type: ignore[method-assign]

    with pytest.raises(ConflictError):
        await service.apply_confirmed_plan(
            draft_id=7,
            tenant_id=1,
            user_id=42,
            next_due_date=date(2027, 1, 1),
        )


@pytest.mark.asyncio
async def test_apply_confirmed_plan_refuses_org_wide() -> None:
    db = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    draft = _pending_draft()
    requirement = _fra_requirement(location_id=None)

    async def _load_draft(**kwargs):
        return draft

    async def _load_req(**kwargs):
        # Simulate the real guard raising
        raise ValidationError(
            "FRA OCR is only available for site-scoped Fire Risk Assessment obligations",
            code="VALIDATION_ERROR",
        )

    service._load_draft = _load_draft  # type: ignore[method-assign]
    service._load_fra_requirement = _load_req  # type: ignore[method-assign]

    with pytest.raises(ValidationError):
        await service.apply_confirmed_plan(
            draft_id=7,
            tenant_id=1,
            user_id=42,
            next_due_date=date(2027, 1, 1),
        )


@pytest.mark.asyncio
async def test_discard_pending_draft() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    draft = _pending_draft()

    async def _load_draft(**kwargs):
        return draft

    service._load_draft = _load_draft  # type: ignore[method-assign]

    storage = MagicMock()
    storage.delete = AsyncMock(return_value=True)

    with (
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.record_audit_event",
            new_callable=AsyncMock,
        ),
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.storage_service",
            return_value=storage,
        ),
    ):
        out = await service.discard_draft(draft_id=7, tenant_id=1, user_id=42, reason="wrong file")

    assert out.status == ComplianceOcrDraftStatus.DISCARDED
    assert out.discarded_at is not None
    storage.delete.assert_awaited()


@pytest.mark.asyncio
async def test_discard_must_not_delete_evidence_blob_when_evidence_asset_id_set() -> None:
    """From-evidence drafts share the occurrence blob — discard must leave it intact."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    evidence_key = "evidence/compliance_record/55/fra.pdf"
    draft = _pending_draft(
        evidence_asset_id=99,
        source_storage_key=evidence_key,
    )

    async def _load_draft(**kwargs):
        return draft

    service._load_draft = _load_draft  # type: ignore[method-assign]

    storage = MagicMock()
    storage.delete = AsyncMock(return_value=True)

    with (
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.record_audit_event",
            new_callable=AsyncMock,
        ) as audit,
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.storage_service",
            return_value=storage,
        ),
    ):
        out = await service.discard_draft(draft_id=7, tenant_id=1, user_id=42, reason="not needed")

    assert out.status == ComplianceOcrDraftStatus.DISCARDED
    storage.delete.assert_not_awaited()
    assert audit.await_count == 1
    payload = audit.await_args.kwargs["payload"]
    assert payload["evidence_asset_id"] == 99
    assert payload["deleted_source_blob"] is False


@pytest.mark.asyncio
async def test_create_draft_from_evidence_asset_happy_path() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    service = ComplianceScheduleFraOcrService(db, ocr_service=MagicMock())
    service._ocr.extract = AsyncMock(return_value=_extraction())

    record = SimpleNamespace(id=55, requirement_id=10, tenant_id=1, reference_number="CRC-1")
    asset = _evidence_asset()
    requirement = _fra_requirement()

    async def _load_record(**kwargs):
        return record

    async def _load_req(**kwargs):
        return requirement

    service._load_record = _load_record  # type: ignore[method-assign]
    service._load_fra_requirement = _load_req  # type: ignore[method-assign]

    storage = MagicMock()
    storage.download = AsyncMock(return_value=asset._content)
    storage.delete = AsyncMock()

    with (
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service._load_bound_evidence_asset",
            new_callable=AsyncMock,
            return_value=asset,
        ),
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.storage_service",
            return_value=storage,
        ),
    ):
        draft = await service.create_draft_from_evidence_asset(
            record_id=55,
            evidence_asset_id=99,
            tenant_id=1,
            user_id=42,
        )

    assert draft.evidence_asset_id == 99
    assert draft.source_storage_key == asset.storage_key
    assert draft.source_checksum_sha256 == asset.checksum_sha256
    storage.delete.assert_not_awaited()
    db.add.assert_called_once()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_create_draft_from_evidence_rejects_non_pdf_magic() -> None:
    db = AsyncMock()
    service = ComplianceScheduleFraOcrService(db, ocr_service=MagicMock())
    record = SimpleNamespace(id=55, requirement_id=10, tenant_id=1, reference_number="CRC-1")
    asset = _evidence_asset(content=b"NOT-A-PDF", checksum_sha256="deadbeef")

    async def _load_record(**kwargs):
        return record

    async def _load_req(**kwargs):
        return _fra_requirement()

    service._load_record = _load_record  # type: ignore[method-assign]
    service._load_fra_requirement = _load_req  # type: ignore[method-assign]

    storage = MagicMock()
    storage.download = AsyncMock(return_value=b"NOT-A-PDF")

    with (
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service._load_bound_evidence_asset",
            new_callable=AsyncMock,
            return_value=asset,
        ),
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.storage_service",
            return_value=storage,
        ),
        pytest.raises(ValidationError, match="does not look like a PDF"),
    ):
        await service.create_draft_from_evidence_asset(
            record_id=55,
            evidence_asset_id=99,
            tenant_id=1,
            user_id=42,
        )


@pytest.mark.asyncio
async def test_create_draft_from_evidence_rejects_over_25mib() -> None:
    from src.domain.services.compliance_schedule_fra_ocr_service import FRA_OCR_MAX_PDF_BYTES

    db = AsyncMock()
    service = ComplianceScheduleFraOcrService(db, ocr_service=MagicMock())
    record = SimpleNamespace(id=55, requirement_id=10, tenant_id=1, reference_number="CRC-1")
    huge = b"%PDF-" + (b"x" * (FRA_OCR_MAX_PDF_BYTES))
    asset = _evidence_asset(content=huge)

    async def _load_record(**kwargs):
        return record

    async def _load_req(**kwargs):
        return _fra_requirement()

    service._load_record = _load_record  # type: ignore[method-assign]
    service._load_fra_requirement = _load_req  # type: ignore[method-assign]

    storage = MagicMock()
    storage.download = AsyncMock(return_value=huge)

    with (
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service._load_bound_evidence_asset",
            new_callable=AsyncMock,
            return_value=asset,
        ),
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.storage_service",
            return_value=storage,
        ),
        pytest.raises(ValidationError, match="25 MiB"),
    ):
        await service.create_draft_from_evidence_asset(
            record_id=55,
            evidence_asset_id=99,
            tenant_id=1,
            user_id=42,
        )


@pytest.mark.asyncio
async def test_create_draft_from_evidence_rejects_checksum_mismatch() -> None:
    db = AsyncMock()
    service = ComplianceScheduleFraOcrService(db, ocr_service=MagicMock())
    record = SimpleNamespace(id=55, requirement_id=10, tenant_id=1, reference_number="CRC-1")
    content = b"%PDF-1.4 ok"
    asset = _evidence_asset(content=content, checksum_sha256="0" * 64)

    async def _load_record(**kwargs):
        return record

    async def _load_req(**kwargs):
        return _fra_requirement()

    service._load_record = _load_record  # type: ignore[method-assign]
    service._load_fra_requirement = _load_req  # type: ignore[method-assign]

    storage = MagicMock()
    storage.download = AsyncMock(return_value=content)

    with (
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service._load_bound_evidence_asset",
            new_callable=AsyncMock,
            return_value=asset,
        ),
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.storage_service",
            return_value=storage,
        ),
        pytest.raises(ValidationError, match="checksum"),
    ):
        await service.create_draft_from_evidence_asset(
            record_id=55,
            evidence_asset_id=99,
            tenant_id=1,
            user_id=42,
        )


@pytest.mark.asyncio
async def test_file_draft_requires_confirmed() -> None:
    db = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    draft = _pending_draft()

    async def _load_draft(**kwargs):
        return draft

    service._load_draft = _load_draft  # type: ignore[method-assign]

    with pytest.raises(ConflictError):
        await service.file_draft_to_library(
            draft_id=7,
            tenant_id=1,
            user=SimpleNamespace(id=42),
            category_id=1,
        )


def test_is_fra_requirement_helpers() -> None:
    ok = _fra_requirement()
    assert ComplianceScheduleFraOcrService._is_fra_requirement(ok) is True

    custom = _fra_requirement(template_id=None, template=None, taxonomy_id="03.01")
    assert ComplianceScheduleFraOcrService._is_fra_requirement(custom) is True

    other = _fra_requirement(
        taxonomy_id="01.01",
        template=SimpleNamespace(template_key="something_else"),
    )
    assert ComplianceScheduleFraOcrService._is_fra_requirement(other) is False


def test_is_fra_ocr_eligible_matches_load_gate() -> None:
    """Template-keyed FRA stays eligible even when taxonomy is not 03.01."""
    template_fra = _fra_requirement(taxonomy_id="03.02")
    assert ComplianceScheduleFraOcrService.is_fra_ocr_eligible(template_fra) is True

    custom = _fra_requirement(template_id=None, template=None, taxonomy_id="03.01")
    assert ComplianceScheduleFraOcrService.is_fra_ocr_eligible(custom) is True

    inactive = _fra_requirement(is_active=False)
    assert ComplianceScheduleFraOcrService.is_fra_ocr_eligible(inactive) is False

    org_wide = _fra_requirement(location_id=None)
    assert ComplianceScheduleFraOcrService.is_fra_ocr_eligible(org_wide) is False

    other = _fra_requirement(
        taxonomy_id="01.01",
        template=SimpleNamespace(template_key="something_else"),
    )
    assert ComplianceScheduleFraOcrService.is_fra_ocr_eligible(other) is False


@pytest.mark.asyncio
async def test_apply_confirmed_plan_flag_off_records_actions_without_capas(monkeypatch) -> None:
    """ACTIONS flag default/off: checked rows are recorded, CAPAs are not created."""
    from src.core.config import settings

    monkeypatch.setattr(settings, "compliance_schedule_fra_ocr_actions_enabled", False)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    requirement = _fra_requirement()
    draft = _pending_draft()

    async def _load_draft(**kwargs):
        return draft

    async def _load_req(**kwargs):
        return requirement

    service._load_draft = _load_draft  # type: ignore[method-assign]
    service._load_fra_requirement = _load_req  # type: ignore[method-assign]

    with (
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.record_audit_event",
            new_callable=AsyncMock,
        ),
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.CAPAAutoService.create_from_fra_ocr_actions",
            new_callable=AsyncMock,
        ) as create_capas,
    ):
        _draft, _req, summary = await service.apply_confirmed_plan(
            draft_id=7,
            tenant_id=1,
            user_id=42,
            next_due_date=date(2027, 3, 14),
            actions=[
                {"index": 0, "text": "Replace fire door seals", "priority_normalised": "high"},
                {"index": 1, "text": "Update escape signage", "priority_normalised": "medium"},
            ],
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

    assert summary["actions_recorded"] == 2
    assert summary["actions_created"] == 0
    create_capas.assert_not_called()


@pytest.mark.asyncio
async def test_apply_confirmed_plan_flag_on_creates_capas_for_checked_rows(monkeypatch) -> None:
    from src.core.config import settings

    monkeypatch.setattr(settings, "compliance_schedule_fra_ocr_actions_enabled", True)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    requirement = _fra_requirement()
    draft = _pending_draft()

    async def _load_draft(**kwargs):
        return draft

    async def _load_req(**kwargs):
        return requirement

    service._load_draft = _load_draft  # type: ignore[method-assign]
    service._load_fra_requirement = _load_req  # type: ignore[method-assign]

    fake_capas = [
        SimpleNamespace(reference_number="CAPA-1"),
        SimpleNamespace(reference_number="CAPA-2"),
    ]

    with (
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.record_audit_event",
            new_callable=AsyncMock,
        ),
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.CAPAAutoService.create_from_fra_ocr_actions",
            new_callable=AsyncMock,
            return_value=fake_capas,
        ) as create_capas,
    ):
        _draft, _req, summary = await service.apply_confirmed_plan(
            draft_id=7,
            tenant_id=1,
            user_id=42,
            next_due_date=date(2027, 3, 14),
            actions=[
                {"index": 0, "text": "Replace fire door seals", "priority_normalised": "high"},
                {"index": 1, "text": "Update escape signage", "priority_normalised": "medium"},
            ],
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

    assert summary["actions_recorded"] == 2
    assert summary["actions_created"] == 2
    create_capas.assert_awaited_once()
    kwargs = create_capas.await_args.kwargs
    assert kwargs["draft_id"] == 7
    assert kwargs["created_by_id"] == 42
    assert len(kwargs["actions"]) == 2


@pytest.mark.asyncio
async def test_apply_confirmed_plan_flag_on_empty_actions_creates_zero(monkeypatch) -> None:
    """Flag on must not invent CAPAs when the operator checked no rows."""
    from src.core.config import settings

    monkeypatch.setattr(settings, "compliance_schedule_fra_ocr_actions_enabled", True)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    requirement = _fra_requirement()
    draft = _pending_draft()

    async def _load_draft(**kwargs):
        return draft

    async def _load_req(**kwargs):
        return requirement

    service._load_draft = _load_draft  # type: ignore[method-assign]
    service._load_fra_requirement = _load_req  # type: ignore[method-assign]

    with (
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.record_audit_event",
            new_callable=AsyncMock,
        ),
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.CAPAAutoService.create_from_fra_ocr_actions",
            new_callable=AsyncMock,
        ) as create_capas,
    ):
        _draft, _req, summary = await service.apply_confirmed_plan(
            draft_id=7,
            tenant_id=1,
            user_id=42,
            next_due_date=date(2027, 3, 14),
            actions=[],
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

    assert summary["actions_recorded"] == 0
    assert summary["actions_created"] == 0
    create_capas.assert_not_called()


@pytest.mark.asyncio
async def test_apply_confirmed_plan_flag_off_records_risk_without_creating(monkeypatch) -> None:
    """RISK flag off: operator scores are recorded, no Enterprise Risk is created."""
    from src.core.config import settings

    monkeypatch.setattr(settings, "compliance_schedule_fra_ocr_risk_enabled", False)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    requirement = _fra_requirement()
    draft = _pending_draft()

    async def _load_draft(**kwargs):
        return draft

    async def _load_req(**kwargs):
        return requirement

    service._load_draft = _load_draft  # type: ignore[method-assign]
    service._load_fra_requirement = _load_req  # type: ignore[method-assign]

    with (
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.record_audit_event",
            new_callable=AsyncMock,
        ),
        patch.object(
            service,
            "_create_risk_from_confirm",
            new_callable=AsyncMock,
        ) as create_risk,
    ):
        _d, _r, summary = await service.apply_confirmed_plan(
            draft_id=7,
            tenant_id=1,
            user_id=42,
            next_due_date=date(2027, 3, 14),
            actions=[],
            risk={"inherent_likelihood": 4, "inherent_impact": 5, "title": "Fire spread"},
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

    assert summary["risks_created"] == 0
    assert draft.confirmed_json["risk"]["inherent_likelihood"] == 4
    create_risk.assert_not_called()


@pytest.mark.asyncio
async def test_apply_confirmed_plan_flag_on_creates_risk_with_operator_scores(monkeypatch) -> None:
    from src.core.config import settings

    monkeypatch.setattr(settings, "compliance_schedule_fra_ocr_risk_enabled", True)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    requirement = _fra_requirement()
    draft = _pending_draft()

    async def _load_draft(**kwargs):
        return draft

    async def _load_req(**kwargs):
        return requirement

    service._load_draft = _load_draft  # type: ignore[method-assign]
    service._load_fra_requirement = _load_req  # type: ignore[method-assign]

    with (
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.record_audit_event",
            new_callable=AsyncMock,
        ),
        patch.object(
            service,
            "_create_risk_from_confirm",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(reference="RISK-0007"),
        ) as create_risk,
    ):
        _d, _r, summary = await service.apply_confirmed_plan(
            draft_id=7,
            tenant_id=1,
            user_id=42,
            next_due_date=date(2027, 3, 14),
            actions=[],
            risk={"inherent_likelihood": 3, "inherent_impact": 4},
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

    assert summary["risks_created"] == 1
    create_risk.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_confirmed_plan_flag_on_without_risk_creates_zero(monkeypatch) -> None:
    """Flag on must not invent a risk from OCR alone when the operator sends none."""
    from src.core.config import settings

    monkeypatch.setattr(settings, "compliance_schedule_fra_ocr_risk_enabled", True)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    service = ComplianceScheduleFraOcrService(db)
    requirement = _fra_requirement()
    draft = _pending_draft()

    async def _load_draft(**kwargs):
        return draft

    async def _load_req(**kwargs):
        return requirement

    service._load_draft = _load_draft  # type: ignore[method-assign]
    service._load_fra_requirement = _load_req  # type: ignore[method-assign]

    with (
        patch(
            "src.domain.services.compliance_schedule_fra_ocr_service.record_audit_event",
            new_callable=AsyncMock,
        ),
        patch.object(
            service,
            "_create_risk_from_confirm",
            new_callable=AsyncMock,
        ) as create_risk,
    ):
        _d, _r, summary = await service.apply_confirmed_plan(
            draft_id=7,
            tenant_id=1,
            user_id=42,
            next_due_date=date(2027, 3, 14),
            actions=[],
            risk=None,
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

    assert summary["risks_created"] == 0
    create_risk.assert_not_called()
