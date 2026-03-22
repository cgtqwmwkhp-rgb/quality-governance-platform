import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.api.routes.compliance import get_compliance_coverage, link_evidence, list_standards
from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkMethod
from src.domain.models.standard import Standard
from src.domain.services.ims_dashboard_service import IMSDashboardService


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

    def all(self):
        return list(self._values)


@pytest.mark.asyncio
async def test_link_evidence_persists_tenant_scoped_links():
    added = []

    async def refresh(link):
        link.id = len(added)
        link.created_at = datetime(2026, 3, 22, tzinfo=timezone.utc)

    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeExecuteResult([])),
        add=lambda obj: added.append(obj),
        commit=AsyncMock(),
        refresh=AsyncMock(side_effect=refresh),
    )
    current_user = types.SimpleNamespace(id=17, email="qa@example.com", tenant_id=91)

    response = await link_evidence(
        types.SimpleNamespace(
            entity_type="document",
            entity_id="DOC-001",
            clause_ids=["9001-7.5", "9001-9.2"],
            linked_by="manual",
            confidence=88.0,
            title="Controlled document",
            notes="Quarterly evidence set",
        ),
        db,
        current_user,
    )

    assert len(added) == 2
    assert all(link.tenant_id == 91 for link in added)
    assert all(link.created_by_id == 17 for link in added)
    assert all(link.created_by_email == "qa@example.com" for link in added)
    assert all(link.linked_by == EvidenceLinkMethod.MANUAL for link in added)
    assert response["message"] == "Upserted 2 evidence link(s)"


@pytest.mark.asyncio
async def test_get_compliance_coverage_uses_persisted_evidence_links():
    persisted_link = ComplianceEvidenceLink(
        tenant_id=12,
        entity_type="audit",
        entity_id="AUD-01",
        clause_id="9001-9.2",
        linked_by=EvidenceLinkMethod.MANUAL,
        confidence=100.0,
    )

    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeExecuteResult([persisted_link])))
    current_user = types.SimpleNamespace(id=5, email="auditor@example.com", tenant_id=12)

    coverage = await get_compliance_coverage(db, current_user, "iso9001")

    assert coverage["partial_coverage"] == 1
    assert coverage["full_coverage"] == 0
    assert coverage["gaps"] > 0


@pytest.mark.asyncio
async def test_list_standards_bridges_db_standard_and_ims_counts():
    persisted_link = ComplianceEvidenceLink(
        tenant_id=44,
        entity_type="policy",
        entity_id="POL-7",
        clause_id="9001-7.5",
        linked_by=EvidenceLinkMethod.MANUAL,
        confidence=75.0,
    )
    canonical_standard = Standard(
        id=101,
        code="ISO9001",
        name="ISO 9001:2015",
        full_name="Quality Management Systems - Requirements",
        version="2015",
    )

    async def execute(statement):
        sql = str(statement)
        if "FROM compliance_evidence_links" in sql:
            return _FakeExecuteResult([persisted_link])
        if "FROM standards" in sql:
            return _FakeExecuteResult([canonical_standard])
        if "FROM clauses" in sql:
            return _FakeExecuteResult([(101, 12)])
        if "FROM ims_requirements" in sql:
            return _FakeExecuteResult([("ISO 9001:2015", 9)])
        raise AssertionError(f"Unexpected statement: {sql}")

    db = types.SimpleNamespace(execute=AsyncMock(side_effect=execute))
    current_user = types.SimpleNamespace(id=8, email="ims@example.com", tenant_id=44)

    standards = await list_standards(db, current_user)
    iso9001 = next(item for item in standards if item.id == "iso9001")

    assert iso9001.db_standard_id == 101
    assert iso9001.db_clause_count == 12
    assert iso9001.ims_requirement_count == 9
    assert iso9001.covered_clauses == 1
    assert iso9001.has_canonical_standard is True


@pytest.mark.asyncio
async def test_ims_dashboard_coverage_counts_full_and_partial_links():
    links = [
        ComplianceEvidenceLink(
            tenant_id=3,
            entity_type="document",
            entity_id="DOC-1",
            clause_id="9001-7.5",
            linked_by=EvidenceLinkMethod.MANUAL,
        ),
        ComplianceEvidenceLink(
            tenant_id=3,
            entity_type="audit",
            entity_id="AUD-2",
            clause_id="9001-7.5",
            linked_by=EvidenceLinkMethod.AUTO,
        ),
        ComplianceEvidenceLink(
            tenant_id=3,
            entity_type="incident",
            entity_id="INC-3",
            clause_id="14001-8.2",
            linked_by=EvidenceLinkMethod.MANUAL,
        ),
    ]
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeExecuteResult(links)))

    summary = await IMSDashboardService(db).get_compliance_coverage()

    assert summary["full_coverage"] == 1
    assert summary["partial_coverage"] == 1
    assert summary["covered_clauses"] == 2
    assert summary["total_evidence_links"] == 3
