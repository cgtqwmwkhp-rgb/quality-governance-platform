from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.domain.models.compliance_evidence import EvidenceLinkMethod
from src.domain.services.external_audit_import_service import ExternalAuditImportService


@pytest.mark.asyncio
async def test_link_evidence_for_finding_revives_soft_deleted_rows() -> None:
    deleted_link = SimpleNamespace(
        deleted_at=datetime.now(timezone.utc),
        linked_by=EvidenceLinkMethod.MANUAL,
        confidence=None,
        title="Old title",
        notes=None,
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: deleted_link)),
        add=Mock(),
        flush=AsyncMock(),
    )
    service = ExternalAuditImportService(db)

    await service._link_evidence_for_finding(
        finding_id=321,
        clause_ids=["iso-9001-8.1"],
        tenant_id=1,
        user_id=1,
        note="Recovered evidence",
        confidence=0.88,
    )

    assert deleted_link.deleted_at is None
    assert deleted_link.linked_by == EvidenceLinkMethod.AUTO
    assert deleted_link.confidence == 0.88
    assert deleted_link.notes == "Recovered evidence"
