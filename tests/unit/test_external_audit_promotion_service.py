"""Path-to-10 S1: promotion collaborator + import facade identity."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.domain.models.compliance_evidence import EvidenceLinkMethod
from src.domain.services.external_audit_import_service import ExternalAuditImportService, PromotionResult
from src.domain.services.external_audit_promotion_service import (
    ExternalAuditPromotionService,
    PromotionResult as DomainPromotionResult,
)


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
