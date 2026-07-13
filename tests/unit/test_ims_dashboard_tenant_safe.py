"""CE-W1: IMS dashboard aggregations must respect tenant boundaries."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.sql import Select

from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkMethod
from src.domain.services.ims_dashboard_service import IMSDashboardService


class _FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


def _select_where_clauses(statement: Select) -> list:
    return list(statement._where_criteria)


@pytest.mark.asyncio
async def test_get_compliance_coverage_scopes_links_to_tenant():
    tenant_links = [
        ComplianceEvidenceLink(
            tenant_id=7,
            entity_type="document",
            entity_id="DOC-1",
            clause_id="9001-7.5",
            linked_by=EvidenceLinkMethod.MANUAL,
        ),
    ]
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeExecuteResult(tenant_links)))
    service = IMSDashboardService(db)

    summary = await service.get_compliance_coverage(tenant_id=7)

    assert summary["total_evidence_links"] == 1
    executed = db.execute.await_args.args[0]
    where_sql = " ".join(str(clause) for clause in _select_where_clauses(executed))
    assert "tenant_id" in where_sql


@pytest.mark.asyncio
async def test_get_audit_schedule_scopes_runs_to_tenant():
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeExecuteResult([])))
    service = IMSDashboardService(db)

    await service.get_audit_schedule(tenant_id=9)

    executed = db.execute.await_args.args[0]
    where_sql = " ".join(str(clause) for clause in _select_where_clauses(executed))
    assert "tenant_id" in where_sql


@pytest.mark.asyncio
async def test_get_standards_compliance_scopes_catalog_to_tenant():
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeExecuteResult([])))
    service = IMSDashboardService(db)

    await service.get_standards_compliance(tenant_id=4)

    executed = db.execute.await_args.args[0]
    where_sql = " ".join(str(clause) for clause in _select_where_clauses(executed))
    assert "tenant_id" in where_sql


@pytest.mark.asyncio
async def test_get_dashboard_passes_tenant_id_to_tenant_scoped_aggregations():
    service = IMSDashboardService(types.SimpleNamespace(execute=AsyncMock()))
    service.get_standards_compliance = AsyncMock(return_value=[])
    service.get_isms_data = AsyncMock(return_value={})
    service.get_uvdb_data = AsyncMock(return_value={})
    service.get_planet_mark_data = AsyncMock(return_value={})
    service.get_compliance_coverage = AsyncMock(return_value={"coverage_percentage": 0})
    service.get_audit_schedule = AsyncMock(return_value=[])

    await service.get_dashboard(tenant_id=12)

    service.get_standards_compliance.assert_awaited_once_with(tenant_id=12)
    service.get_compliance_coverage.assert_awaited_once_with(tenant_id=12)
    service.get_audit_schedule.assert_awaited_once_with(tenant_id=12)
    service.get_isms_data.assert_awaited_once_with(tenant_id=12)
