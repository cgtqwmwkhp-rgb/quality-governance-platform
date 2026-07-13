"""Route-level tests for GET /api/v1/compliance/audit-pack provenance export."""

from __future__ import annotations

import json
import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.api.routes.compliance import export_audit_pack
from src.domain.models.compliance_evidence import (
    ComplianceEvidenceLink,
    EvidenceLinkMethod,
    EvidenceLinkStatus,
)


class _FakeScalarResult:
    def __init__(self, values):
        self._values = list(values)

    def all(self):
        return list(self._values)


class _FakeExecuteResult:
    def __init__(self, values=None):
        self._values = list(values or [])

    def scalars(self):
        return _FakeScalarResult(self._values)


def _cel(
    *,
    link_id: int,
    signal_type: str | None,
    entity_type: str = "document",
    entity_id: str = "DOC-1",
    clause_id: str = "9001-7.5",
    status: EvidenceLinkStatus = EvidenceLinkStatus.CONFIRMED,
) -> ComplianceEvidenceLink:
    now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    link = ComplianceEvidenceLink(
        tenant_id=42,
        entity_type=entity_type,
        entity_id=entity_id,
        clause_id=clause_id,
        linked_by=EvidenceLinkMethod.AI,
        confidence=0.88,
        status=status,
        scheme="iso9001",
        rationale="AI mapping rationale for auditor review",
        signal_type=signal_type,
        title="Link title",
        notes="notes",
        created_by_id=7,
        created_by_email="mapper@example.com",
        auto_applied=False,
    )
    link.id = link_id
    link.created_at = now
    link.updated_at = now
    return link


@pytest.mark.asyncio
async def test_audit_pack_excludes_nonconformity_by_default():
    links = [
        _cel(link_id=1, signal_type="evidence"),
        _cel(
            link_id=2,
            signal_type="nonconformity",
            entity_type="incident",
            entity_id="INC-9",
        ),
    ]
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeExecuteResult(links)))
    current_user = types.SimpleNamespace(id=7, email="auditor@example.com", tenant_id=42)

    response = await export_audit_pack(
        db,
        current_user,
        standard="iso9001",
        include_nonconformity=False,
        include_soa=False,
        organization_name="Plantexpand",
    )

    assert response.media_type == "application/json"
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["x-audit-pack-nonconformity-mode"] == "excluded_from_conformance_evidence"

    pack = json.loads(response.body.decode("utf-8"))
    assert pack["pack_version"] == "gkb-wl1-1.0"
    assert pack["exported_by"] == "auditor@example.com"
    assert pack["counts"]["conformance_evidence_links"] == 1
    assert pack["counts"]["operational_signal_links"] == 1
    assert len(pack["evidence_links"]) == 1
    evidence = pack["evidence_links"][0]
    assert evidence["signal_type"] == "evidence"
    assert evidence["rationale"] == "AI mapping rationale for auditor review"
    assert evidence["created_by"] == "mapper@example.com"
    assert evidence["scheme"] == "iso9001"
    assert evidence["clause_id"] == "9001-7.5"
    assert evidence["status"] == "confirmed"
    assert evidence["confirmed_at"] is not None
    assert pack["operational_signals"][0]["signal_type"] == "nonconformity"
    assert pack["operational_signals"][0]["signal_label"] == "operational_nonconformity"
    assert pack["operational_signals"][0]["conformance_eligible"] is False


@pytest.mark.asyncio
async def test_audit_pack_labels_nonconformity_when_included():
    links = [
        _cel(link_id=1, signal_type="evidence"),
        _cel(
            link_id=2,
            signal_type="nonconformity",
            entity_type="incident",
            entity_id="INC-9",
        ),
    ]
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeExecuteResult(links)))
    current_user = types.SimpleNamespace(id=7, email="auditor@example.com", tenant_id=42)

    response = await export_audit_pack(
        db,
        current_user,
        standard=None,
        include_nonconformity=True,
        include_soa=False,
        organization_name="Plantexpand",
    )

    pack = json.loads(response.body.decode("utf-8"))
    assert pack["provenance_policy"]["nonconformity_mode"] == "labelled_in_pack"
    assert pack["counts"]["exported_evidence_links"] == 2
    nc = next(row for row in pack["evidence_links"] if row["signal_type"] == "nonconformity")
    assert nc["conformance_eligible"] is False
    assert nc["signal_label"] == "operational_nonconformity"
    assert response.headers["x-audit-pack-nonconformity-mode"] == "labelled_in_pack"
