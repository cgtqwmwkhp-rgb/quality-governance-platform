"""PR-E4 — governed-knowledge ingest writes CEL through the sole writer."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.compliance_evidence import EvidenceCoverKind, EvidenceLinkMethod, EvidenceLinkStatus
from src.domain.services.compliance_evidence_link_writer import (
    apply_ingest_mapping,
    apply_promotion_mapping,
    remaining_writer_report,
)


class _ScalarResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


@pytest.mark.asyncio
async def test_new_auto_confirm_does_not_stamp_a_human(monkeypatch):
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(None))
    db.add = MagicMock()

    async def _no_pin(*_a, **_k):
        return None

    monkeypatch.setattr(
        "src.domain.services.cel_version_pin.pin_evidence_link_document_version",
        _no_pin,
    )

    link, preserved = await apply_ingest_mapping(
        db,
        tenant_id=1,
        entity_type="document",
        entity_id="55",
        clause_id="9001-7.2",
        status=EvidenceLinkStatus.CONFIRMED,
        auto_applied=True,
        actor_id=7,
        actor_email="ai@example.com",
        scheme="iso9001",
        confidence=0.99,
        title="Policy",
    )
    assert preserved is False
    assert link.linked_by == EvidenceLinkMethod.AI
    assert link.status == EvidenceLinkStatus.CONFIRMED
    assert link.auto_applied is True
    assert link.confirmed_by_id is None
    assert link.cover_kind == EvidenceCoverKind.EVIDENCES
    db.add.assert_called_once_with(link)


@pytest.mark.asyncio
async def test_existing_human_stamp_is_preserved(monkeypatch):
    existing = SimpleNamespace(
        confirmed_by_id=42,
        confirmed_at=datetime.now(timezone.utc),
        linked_by=EvidenceLinkMethod.MANUAL,
        status=EvidenceLinkStatus.CONFIRMED,
        auto_applied=False,
        title="Human title",
        scheme=None,
        confidence=None,
        rationale=None,
        signal_type="evidence",
        clause_id="9001-7.5",
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(existing))
    db.add = MagicMock()

    link, preserved = await apply_ingest_mapping(
        db,
        tenant_id=1,
        entity_type="document",
        entity_id="9",
        clause_id="9001-7.5",
        status=EvidenceLinkStatus.PROPOSED,
        auto_applied=False,
        actor_id=99,
        scheme="iso9001",
        confidence=0.4,
        rationale="ai guess",
        title="Would overwrite",
    )
    assert preserved is True
    assert link is existing
    assert link.confirmed_by_id == 42
    assert link.status == EvidenceLinkStatus.CONFIRMED
    assert link.linked_by == EvidenceLinkMethod.MANUAL
    assert link.title == "Human title"
    assert link.confidence == 0.4
    db.add.assert_not_called()


def test_gks_is_no_longer_on_the_remaining_writer_list():
    paths = {row["path"] for row in remaining_writer_report()}
    assert "src/domain/services/governed_knowledge_service.py" not in paths
    assert "src/domain/services/builder_standard_link_service.py" not in paths
    assert "src/domain/services/external_audit_promotion_service.py" not in paths
    assert "src/domain/services/audit_service.py" in paths


@pytest.mark.asyncio
async def test_promotion_mapping_revives_soft_deleted_row():
    deleted = SimpleNamespace(
        deleted_at=datetime.now(timezone.utc),
        linked_by=EvidenceLinkMethod.MANUAL,
        confidence=None,
        title="Old title",
        notes=None,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(deleted))
    db.add = MagicMock()

    link = await apply_promotion_mapping(
        db,
        tenant_id=1,
        entity_type="audit_finding",
        entity_id="321",
        clause_id="iso-9001-8.1",
        actor_id=1,
        title="Imported audit evidence for finding 321",
        notes="Recovered evidence",
        confidence=0.88,
    )
    assert link is deleted
    assert deleted.deleted_at is None
    assert deleted.linked_by == EvidenceLinkMethod.AUTO
    assert deleted.confidence == 0.88
    assert deleted.notes == "Recovered evidence"
    db.add.assert_not_called()
