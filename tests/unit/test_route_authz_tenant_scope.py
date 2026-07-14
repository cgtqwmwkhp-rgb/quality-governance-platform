"""Route-level tenant authz: exact tenant match, no NULL-inclusive OR on list endpoints."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from src.api.utils.tenant import apply_tenant_filter, require_tenant_id
from src.domain.models.audit import AuditFinding, AuditRun, AuditTemplate
from src.domain.models.incident import IncidentRunningSheetEntry
from src.domain.models.risk import Risk
from src.domain.services.audit_service import AuditService


def _sql(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True})).upper()


def _assert_exact_tenant_sql(sql: str, tenant_id: int = 42) -> None:
    """Assert exact tenant equality; allow unrelated IS NULL (e.g. archived_at)."""
    assert "TENANT_ID" in sql
    assert f"= {tenant_id}" in sql or f"={tenant_id}" in sql
    compact = " ".join(sql.split())
    assert "TENANT_ID IS NULL" not in compact
    # NULL-inclusive sharing: tenant_id = N OR ... tenant_id IS NULL
    assert " OR " not in _tenant_where_fragment(compact)


def _tenant_where_fragment(sql: str) -> str:
    """Return AND-split clauses that mention TENANT_ID."""
    return " AND ".join(chunk for chunk in sql.split(" AND ") if "TENANT_ID" in chunk)


# ---------------------------------------------------------------------------
# AuditService list_* helpers (follow-up to #584 _get_entity)
# ---------------------------------------------------------------------------


class _FakeScalars:
    def all(self):
        return []


class _FakeResult:
    def __init__(self, scalar_value=0):
        self._scalar_value = scalar_value

    def scalar_one(self):
        return self._scalar_value

    def scalars(self):
        return _FakeScalars()


@pytest.mark.asyncio
async def test_audit_service_list_templates_sql_exact_tenant_only():
    captured: list = []

    async def _execute(stmt):
        captured.append(stmt)
        return _FakeResult(0)

    service = AuditService(db=SimpleNamespace(execute=_execute))
    await service.list_templates(tenant_id=42, page=1, page_size=20)

    assert captured, "expected count + page queries"
    for stmt in captured:
        _assert_exact_tenant_sql(_sql(stmt), 42)


@pytest.mark.asyncio
async def test_audit_service_list_runs_sql_exact_tenant_only():
    captured: list = []

    async def _execute(stmt):
        captured.append(stmt)
        return _FakeResult(0)

    service = AuditService(db=SimpleNamespace(execute=_execute))
    await service.list_runs(42, page=1, page_size=20)

    for stmt in captured:
        _assert_exact_tenant_sql(_sql(stmt), 42)


@pytest.mark.asyncio
async def test_audit_service_list_findings_sql_exact_tenant_only():
    captured: list = []

    async def _execute(stmt):
        captured.append(stmt)
        return _FakeResult(0)

    service = AuditService(db=SimpleNamespace(execute=_execute))
    await service.list_findings(42, page=1, page_size=20)

    for stmt in captured:
        _assert_exact_tenant_sql(_sql(stmt), 42)


def test_audit_service_list_helpers_source_no_null_inclusive_or():
    for name in ("list_templates", "list_runs", "list_findings"):
        source = inspect.getsource(getattr(AuditService, name))
        assert "tenant_id.is_(None)" not in source, f"{name} still has tenant_id.is_(None)"
        assert "or_(" not in source, f"{name} still has or_("


# ---------------------------------------------------------------------------
# Route SQL / require_tenant_id behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audits_list_templates_uses_exact_tenant_filter():
    from src.api.routes import audits as audits_routes

    statements: list = []

    async def scalar(statement):
        statements.append(statement)
        return 0

    async def execute(statement):
        statements.append(statement)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    db = SimpleNamespace(scalar=AsyncMock(side_effect=scalar), execute=AsyncMock(side_effect=execute))
    user = SimpleNamespace(tenant_id=17, is_superuser=False)
    params = SimpleNamespace(page=1, page_size=20)

    await audits_routes.list_templates(
        db=db,
        current_user=user,
        params=params,
        search=None,
        category=None,
        audit_type=None,
        is_published=None,
    )

    assert statements
    for stmt in statements:
        sql = _sql(stmt)
        _assert_exact_tenant_sql(sql, 17)


@pytest.mark.asyncio
async def test_audits_list_templates_requires_tenant():
    from src.api.routes import audits as audits_routes

    db = SimpleNamespace(scalar=AsyncMock(), execute=AsyncMock())
    user = SimpleNamespace(tenant_id=None, is_superuser=False)
    params = SimpleNamespace(page=1, page_size=20)

    with pytest.raises(HTTPException) as exc:
        await audits_routes.list_templates(
            db=db,
            current_user=user,
            params=params,
            search=None,
            category=None,
            audit_type=None,
            is_published=None,
        )
    assert exc.value.status_code == 403
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_audit_templates_list_categories_exact_tenant():
    from src.api.routes import audit_templates as at_routes

    statements: list = []

    async def execute(statement):
        statements.append(statement)
        result = MagicMock()
        result.all.return_value = []
        return result

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    user = SimpleNamespace(tenant_id=9)

    await at_routes.list_categories(db=db, user=user)

    sql = _sql(statements[0])
    _assert_exact_tenant_sql(sql, 9)


@pytest.mark.asyncio
async def test_audit_templates_list_categories_requires_tenant():
    from src.api.routes import audit_templates as at_routes

    db = SimpleNamespace(execute=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await at_routes.list_categories(db=db, user=SimpleNamespace(tenant_id=None))
    assert exc.value.status_code == 403
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_risks_list_uses_require_and_apply_tenant_filter():
    from src.api.routes import risks as risks_routes

    statements: list = []

    async def scalar(statement):
        statements.append(statement)
        return 0

    async def execute(statement):
        statements.append(statement)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    db = SimpleNamespace(scalar=AsyncMock(side_effect=scalar), execute=AsyncMock(side_effect=execute))
    user = SimpleNamespace(tenant_id=55, is_superuser=False)

    await risks_routes.list_risks(
        db=db,
        current_user=user,
        page=1,
        page_size=20,
        search=None,
        category=None,
        status_filter=None,
        risk_level=None,
        owner_id=None,
    )

    assert statements
    for stmt in statements:
        sql = _sql(stmt)
        _assert_exact_tenant_sql(sql, 55)


@pytest.mark.asyncio
async def test_risks_list_requires_tenant():
    from src.api.routes import risks as risks_routes

    db = SimpleNamespace(scalar=AsyncMock(), execute=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await risks_routes.list_risks(
            db=db,
            current_user=SimpleNamespace(tenant_id=None, is_superuser=False),
            page=1,
            page_size=20,
            search=None,
            category=None,
            status_filter=None,
            risk_level=None,
            owner_id=None,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_documents_scope_requires_tenant():
    from src.api.routes.documents import _scope_stmt_to_current_tenant
    from src.domain.models.document import Document

    stmt = select(Document)
    with pytest.raises(HTTPException) as exc:
        _scope_stmt_to_current_tenant(stmt, Document.tenant_id, SimpleNamespace(tenant_id=None, is_superuser=False))
    assert exc.value.status_code == 403


def test_documents_scope_exact_tenant_sql():
    from src.api.routes.documents import _scope_stmt_to_current_tenant
    from src.domain.models.document import Document

    stmt = select(Document)
    scoped = _scope_stmt_to_current_tenant(stmt, Document.tenant_id, SimpleNamespace(tenant_id=12, is_superuser=False))
    sql = _sql(scoped)
    _assert_exact_tenant_sql(sql, 12)


@pytest.mark.asyncio
async def test_incident_running_sheet_list_exact_tenant_no_null_path():
    from src.api.routes import incidents as incidents_routes

    statements: list = []

    async def execute(statement):
        statements.append(statement)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    incident = SimpleNamespace(id=7, tenant_id=None)  # previously triggered IS NULL path
    svc = SimpleNamespace(get_incident=AsyncMock(return_value=incident))

    # Patch IncidentService constructor used inside the route
    original = incidents_routes.IncidentService
    incidents_routes.IncidentService = lambda db: svc
    try:
        db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
        user = SimpleNamespace(tenant_id=33, is_superuser=False)
        await incidents_routes.list_incident_running_sheet_entries(incident_id=7, db=db, current_user=user)
    finally:
        incidents_routes.IncidentService = original

    assert statements
    sql = _sql(statements[0])
    _assert_exact_tenant_sql(sql, 33)


@pytest.mark.asyncio
async def test_incident_running_sheet_requires_tenant():
    from src.api.routes import incidents as incidents_routes

    incident = SimpleNamespace(id=7, tenant_id=3)
    svc = SimpleNamespace(get_incident=AsyncMock(return_value=incident))
    original = incidents_routes.IncidentService
    incidents_routes.IncidentService = lambda db: svc
    try:
        db = SimpleNamespace(execute=AsyncMock())
        with pytest.raises(HTTPException) as exc:
            await incidents_routes.list_incident_running_sheet_entries(
                incident_id=7,
                db=db,
                current_user=SimpleNamespace(tenant_id=None, is_superuser=False),
            )
        assert exc.value.status_code == 403
    finally:
        incidents_routes.IncidentService = original


@pytest.mark.asyncio
async def test_complaints_list_requires_tenant_for_non_superuser():
    from src.api.routes import complaints as complaints_routes

    with pytest.raises(HTTPException) as exc:
        await complaints_routes.list_complaints(
            db=AsyncMock(),
            current_user=SimpleNamespace(
                id=1, email="a@b.c", is_superuser=False, tenant_id=None, has_permission=lambda *_: False
            ),
            request_id="t",
            page=1,
            page_size=20,
            status_filter=None,
            complainant_email=None,
            owner=None,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_near_miss_list_requires_tenant_for_non_superuser():
    from src.api.routes import near_miss as near_miss_routes

    with pytest.raises(HTTPException) as exc:
        await near_miss_routes.list_near_misses(
            db=AsyncMock(),
            current_user=SimpleNamespace(id=1, email="a@b.c", is_superuser=False, tenant_id=None),
            page=1,
            page_size=20,
            status_filter=None,
            priority=None,
            contract=None,
            reporter_email=None,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_rtas_list_requires_tenant_for_non_superuser():
    from src.api.routes import rtas as rtas_routes

    with pytest.raises(HTTPException) as exc:
        await rtas_routes.list_rtas(
            db=AsyncMock(),
            current_user=SimpleNamespace(
                id=1, email="a@b.c", is_superuser=False, tenant_id=None, has_permission=lambda *_: False
            ),
            request_id="t",
            page=1,
            page_size=10,
            severity=None,
            status_filter=None,
            reporter_email=None,
        )
    assert exc.value.status_code == 403


def test_apply_tenant_filter_pattern_on_models():
    """Sanity: shared helper exact-match SQL for models used by fixed routes."""
    for model, tid in ((AuditTemplate, 1), (AuditRun, 2), (AuditFinding, 3), (Risk, 4), (IncidentRunningSheetEntry, 5)):
        filtered = apply_tenant_filter(select(model), model, tid)
        sql = _sql(filtered)
        _assert_exact_tenant_sql(sql, tid)


def test_route_source_guards_drop_null_inclusive_list_patterns():
    """Guards for the specific list endpoints we fixed (not every audits.py lookup)."""
    from src.api.routes import audit_templates, audits, complaints, documents, incidents, near_miss, risks, rtas

    # audits.list_templates body must use helpers, not or_/is_(None)
    src = inspect.getsource(audits.list_templates)
    assert "require_tenant_id" in src
    assert "apply_tenant_filter" in src
    assert "tenant_id.is_(None)" not in src
    assert "or_(" not in src

    src = inspect.getsource(audit_templates.list_categories)
    assert "apply_tenant_filter" in src
    assert "tenant_id.is_(None)" not in src
    assert "or_(" not in src

    src = inspect.getsource(incidents.list_incident_running_sheet_entries)
    assert "apply_tenant_filter" in src
    assert "tenant_id.is_(None)" not in src

    src = inspect.getsource(risks.list_risks)
    assert "require_tenant_id" in src
    assert "apply_tenant_filter" in src

    src = inspect.getsource(documents._scope_stmt_to_current_tenant)
    assert "require_tenant_id" in src

    src = inspect.getsource(complaints.list_complaints)
    assert "require_tenant_id" in src
    assert "apply_tenant_filter" in src
    assert "tenant_id.is_(None)" not in src
    assert "or_(" not in src

    src = inspect.getsource(near_miss.list_near_misses)
    assert "require_tenant_id" in src
    assert "apply_tenant_filter" in src
    assert "tenant_id.is_(None)" not in src

    src = inspect.getsource(rtas.list_rtas)
    assert "require_tenant_id" in src
    assert "apply_tenant_filter" in src
    assert "tenant_id.is_(None)" not in src


def test_require_tenant_id_still_403():
    with pytest.raises(HTTPException) as exc:
        require_tenant_id(None)
    assert exc.value.status_code == 403
