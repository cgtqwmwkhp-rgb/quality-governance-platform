"""SEC-01: evidence tenant isolation.

Covers the H&S rich reporting Wave 0 security fixes:

- ``validate_source_exists`` must scope the source-record lookup to the
  caller's tenant and fail closed with 404 (not 403) so cross-tenant IDOR
  probing can't distinguish "doesn't exist" from "exists in another tenant".
- ``link_asset_to_investigation`` must scope the investigation lookup to
  the caller's tenant.
- ``InvestigationService.get_source_evidence_assets`` must filter by
  tenant when a tenant_id is supplied (investigation evidence handoff).
- ``InvestigationService.generate_pack_for_investigation`` must scope its
  evidence-asset query (customer pack) to the investigation's tenant.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.routes.evidence_assets import link_asset_to_investigation, validate_source_exists
from src.domain.exceptions import NotFoundError
from src.domain.models.investigation import AssignedEntityType
from src.domain.services.investigation_service import InvestigationService


class _Result:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return [] if self.value is None else list(self.value)


def _sql(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True})).lower()


# ---------------------------------------------------------------------------
# validate_source_exists — evidence upload/list source validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_source_exists_scopes_lookup_to_caller_tenant():
    statements = []

    async def execute(stmt):
        statements.append(stmt)
        return _Result(None)

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))

    with pytest.raises(NotFoundError):
        await validate_source_exists("near_miss", 5, db, tenant_id=7)

    assert statements
    sql = _sql(statements[0])
    assert "tenant_id = 7" in sql
    assert "id = 5" in sql


@pytest.mark.asyncio
async def test_validate_source_exists_denies_cross_tenant_source_with_404_not_403():
    """Fail closed: cross-tenant source lookup raises NotFoundError (404), not 403 — avoids IDOR enumeration."""
    db = SimpleNamespace(execute=AsyncMock(return_value=_Result(None)))

    with pytest.raises(NotFoundError) as exc:
        await validate_source_exists("incident", 42, db, tenant_id=99)

    assert exc.value.http_status == 404
    assert exc.value.code == "SOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_validate_source_exists_succeeds_for_same_tenant_source():
    fake_incident = SimpleNamespace(id=42, tenant_id=99)
    db = SimpleNamespace(execute=AsyncMock(return_value=_Result(fake_incident)))

    assert await validate_source_exists("incident", 42, db, tenant_id=99) is True


@pytest.mark.asyncio
async def test_validate_source_exists_skips_validation_for_polymorphic_action_source():
    """Actions are polymorphic and validated separately upstream; unaffected by the tenant fix."""
    db = SimpleNamespace(execute=AsyncMock())

    assert await validate_source_exists("action", 0, db, tenant_id=1) is True
    db.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# link_asset_to_investigation — evidence <-> investigation linking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_link_asset_to_investigation_denies_cross_tenant_investigation():
    """A same-tenant asset must not be linkable to another tenant's investigation."""
    statements = []
    fake_asset = SimpleNamespace(id=1, linked_investigation_id=None, updated_by_id=None)

    async def execute(stmt):
        statements.append(stmt)
        if len(statements) == 1:
            return _Result(fake_asset)
        return _Result(None)  # investigation belongs to another tenant

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    current_user = SimpleNamespace(id=1, tenant_id=7)

    with pytest.raises(NotFoundError) as exc:
        await link_asset_to_investigation(
            asset_id=1,
            investigation_id=999,
            db=db,
            current_user=current_user,
        )

    assert exc.value.http_status == 404
    assert exc.value.code == "INVESTIGATION_NOT_FOUND"
    assert len(statements) == 2
    sql = _sql(statements[1])
    assert "tenant_id = 7" in sql
    assert fake_asset.linked_investigation_id is None  # never mutated


@pytest.mark.asyncio
async def test_link_asset_to_investigation_succeeds_for_same_tenant_investigation():
    fake_asset = SimpleNamespace(id=1, linked_investigation_id=None, updated_by_id=None)
    fake_investigation = SimpleNamespace(id=55, tenant_id=7)

    statements = []

    async def execute(stmt):
        statements.append(stmt)
        if len(statements) == 1:
            return _Result(fake_asset)
        return _Result(fake_investigation)

    db = SimpleNamespace(
        execute=AsyncMock(side_effect=execute),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    current_user = SimpleNamespace(id=1, tenant_id=7)

    result = await link_asset_to_investigation(
        asset_id=1,
        investigation_id=55,
        db=db,
        current_user=current_user,
    )

    assert result.linked_investigation_id == 55
    db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# InvestigationService.get_source_evidence_assets — evidence handoff on
# investigation creation from a source record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_source_evidence_assets_filters_by_tenant_when_provided():
    statements = []

    async def execute(stmt):
        statements.append(stmt)
        return _Result([])

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))

    await InvestigationService.get_source_evidence_assets(
        db,
        AssignedEntityType.REPORTING_INCIDENT,
        123,
        tenant_id=11,
    )

    assert statements
    sql = _sql(statements[0])
    assert "tenant_id = 11" in sql


@pytest.mark.asyncio
async def test_create_from_record_passes_tenant_id_into_evidence_handoff():
    """Guardrail: the evidence-link call site inside create_from_record must be tenant-scoped."""
    source = inspect.getsource(InvestigationService.create_from_record)
    assert "get_source_evidence_assets(db, source_type_enum, source_id, tenant_id=tenant_id)" in source


# ---------------------------------------------------------------------------
# InvestigationService.generate_pack_for_investigation — customer pack
# evidence-asset query must not cross tenants
# ---------------------------------------------------------------------------


def test_generate_pack_for_investigation_scopes_evidence_assets_to_tenant():
    """Guardrail: the customer-pack evidence query must filter on EvidenceAsset.tenant_id."""
    source = inspect.getsource(InvestigationService.generate_pack_for_investigation)
    assert "EvidenceAsset.tenant_id == tenant_id" in source
