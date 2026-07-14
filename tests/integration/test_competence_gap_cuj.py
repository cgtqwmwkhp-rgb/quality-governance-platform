"""Integration-style CUJ checks for competence gap closed loop (service contracts)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.competence_gap import CompetenceGapSignalType, CompetenceGapStatus
from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkMethod, EvidenceSignalType
from src.domain.services.competence_gap_service import competence_gap_service


@pytest.mark.asyncio
async def test_assessor_confirm_hook_opens_gap_for_nonconformity():
    link = ComplianceEvidenceLink(
        tenant_id=1,
        entity_type="audit_finding",
        entity_id="99",
        clause_id="7.2",
        linked_by=EvidenceLinkMethod.AI,
        signal_type=EvidenceSignalType.NONCONFORMITY.value,
        confidence=0.88,
        rationale="Competence not demonstrated",
    )
    link.id = 55

    prior = MagicMock()
    prior.scalar_one_or_none.return_value = None
    db = SimpleNamespace(
        execute=AsyncMock(return_value=prior),
        add=MagicMock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    async def flush_side_effect():
        for call in db.add.call_args_list:
            obj = call.args[0]
            if getattr(obj, "source_id", None) == 55 and getattr(obj, "id", None) is None:
                obj.id = 1001

    db.flush.side_effect = flush_side_effect

    with patch(
        "src.domain.services.competence_gap_service.record_audit_event",
        new=AsyncMock(),
    ):
        gap = await competence_gap_service.from_evidence_link(
            db,
            link=link,
            created_by_id=2,
            tenant_id=1,
            commit=True,
        )

    assert gap is not None
    assert gap.id == 1001
    assert gap.signal_type == CompetenceGapSignalType.NONCONFORMITY
    assert gap.status == CompetenceGapStatus.OPEN
    assert gap.source_type == "compliance_evidence_link"
    assert gap.source_id == 55


@pytest.mark.asyncio
async def test_assessor_confirm_skips_evidence_signal():
    link = ComplianceEvidenceLink(
        tenant_id=1,
        entity_type="document",
        entity_id="1",
        clause_id="4.1",
        linked_by=EvidenceLinkMethod.AI,
        signal_type=EvidenceSignalType.EVIDENCE.value,
    )
    link.id = 7
    db = SimpleNamespace()
    gap = await competence_gap_service.from_evidence_link(
        db,
        link=link,
        created_by_id=1,
        tenant_id=1,
        commit=False,
    )
    assert gap is None
