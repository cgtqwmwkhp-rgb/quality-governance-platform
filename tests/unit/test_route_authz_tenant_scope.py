"""Route-level tenant authz: exact tenant match, no NULL-inclusive OR on list endpoints."""

from __future__ import annotations

import ast
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


# ---------------------------------------------------------------------------
# Superuser twins of the list endpoints above (B-13 siblings)
#
# `list_near_misses`, `list_rtas`, `list_complaints` and `list_risks` each
# guarded the tenant filter with an inline `if not current_user.is_superuser:`,
# which is the same defect B-13 fixed on the incident register expressed a
# different way: the register spanned every tenant while the executive
# dashboard tile beside it (`complaints.register_total`, `rtas.total`) stayed
# scoped to the caller's own, so the two surfaces described different
# populations. `list_risks` has no dashboard twin to contradict, but `risks`
# is a FORCE-RLS table of C3-confidential rows whose policies are inert under
# the application's `rolbypassrls` connection, so the route predicate is the
# only thing scoping the read at all.
#
# Access to a single cross-tenant record by id is untouched on every one of
# them — only the enumeration is withdrawn.
# ---------------------------------------------------------------------------


def _superuser(tenant_id: int | None) -> SimpleNamespace:
    return SimpleNamespace(
        id=2,
        email="root@test.example.com",
        is_superuser=True,
        tenant_id=tenant_id,
        has_permission=lambda *_: True,
    )


class _CountThenRowsResult:
    """One result object that answers both the count query and the page query."""

    def __init__(self, count: int = 0):
        self._count = count

    def scalar(self):
        return self._count

    def scalar_one(self):
        return self._count

    def scalars(self):
        return self

    def all(self):
        return []


def _capturing_db() -> tuple[SimpleNamespace, list]:
    statements: list = []

    async def execute(statement):
        statements.append(statement)
        return _CountThenRowsResult()

    return SimpleNamespace(execute=AsyncMock(side_effect=execute)), statements


@pytest.mark.asyncio
async def test_near_miss_list_scopes_a_superuser_to_their_own_tenant():
    from src.api.routes import near_miss as near_miss_routes

    db, statements = _capturing_db()

    await near_miss_routes.list_near_misses(
        db=db,
        current_user=_superuser(77),
        page=1,
        page_size=20,
        status_filter=None,
        priority=None,
        contract=None,
        reporter_email=None,
        asset_id=None,
        ids=None,
    )

    assert statements, "expected count + page queries"
    for stmt in statements:
        _assert_exact_tenant_sql(_sql(stmt), 77)


@pytest.mark.asyncio
async def test_near_miss_list_requires_tenant_for_a_superuser():
    from src.api.routes import near_miss as near_miss_routes

    db, statements = _capturing_db()

    with pytest.raises(HTTPException) as exc:
        await near_miss_routes.list_near_misses(
            db=db,
            current_user=_superuser(None),
            page=1,
            page_size=20,
            status_filter=None,
            priority=None,
            contract=None,
            reporter_email=None,
            asset_id=None,
            ids=None,
        )
    assert exc.value.status_code == 403
    assert not statements, "a tenantless caller must not reach the database"


@pytest.mark.asyncio
async def test_rtas_list_scopes_a_superuser_to_their_own_tenant():
    from src.api.routes import rtas as rtas_routes

    db, statements = _capturing_db()

    await rtas_routes.list_rtas(
        db=db,
        current_user=_superuser(77),
        request_id="req-superuser-rta-list",
        page=1,
        page_size=10,
        severity=None,
        status_filter=None,
        reporter_email=None,
        asset_id=None,
        ids=None,
    )

    assert statements, "expected count + page queries"
    for stmt in statements:
        _assert_exact_tenant_sql(_sql(stmt), 77)


@pytest.mark.asyncio
async def test_rtas_list_requires_tenant_for_a_superuser():
    from src.api.routes import rtas as rtas_routes

    db, statements = _capturing_db()

    with pytest.raises(HTTPException) as exc:
        await rtas_routes.list_rtas(
            db=db,
            current_user=_superuser(None),
            request_id="req-superuser-rta-list",
            page=1,
            page_size=10,
            severity=None,
            status_filter=None,
            reporter_email=None,
            asset_id=None,
            ids=None,
        )
    # 403 must survive the broad `except Exception` that turns query faults into
    # 500/503 in this handler, so assert the code rather than just the raise.
    assert exc.value.status_code == 403
    assert not statements, "a tenantless caller must not reach the database"


@pytest.mark.asyncio
async def test_complaints_list_scopes_a_superuser_to_their_own_tenant():
    from src.api.routes import complaints as complaints_routes

    db, statements = _capturing_db()

    await complaints_routes.list_complaints(
        db=db,
        current_user=_superuser(77),
        request_id="req-superuser-complaint-list",
        page=1,
        page_size=20,
        status_filter=None,
        complainant_email=None,
        owner=None,
        ids=None,
    )

    assert statements, "expected count + page queries"
    for stmt in statements:
        _assert_exact_tenant_sql(_sql(stmt), 77)


@pytest.mark.asyncio
async def test_complaints_list_requires_tenant_for_a_superuser():
    from src.api.routes import complaints as complaints_routes

    db, statements = _capturing_db()

    with pytest.raises(HTTPException) as exc:
        await complaints_routes.list_complaints(
            db=db,
            current_user=_superuser(None),
            request_id="req-superuser-complaint-list",
            page=1,
            page_size=20,
            status_filter=None,
            complainant_email=None,
            owner=None,
            ids=None,
        )
    assert exc.value.status_code == 403
    assert not statements, "a tenantless caller must not reach the database"


def _capturing_db_with_scalar() -> tuple[SimpleNamespace, list]:
    """`list_risks` counts through `db.scalar` and pages through `db.execute`."""
    statements: list = []

    async def scalar(statement):
        statements.append(statement)
        return 0

    async def execute(statement):
        statements.append(statement)
        return _CountThenRowsResult()

    return (
        SimpleNamespace(scalar=AsyncMock(side_effect=scalar), execute=AsyncMock(side_effect=execute)),
        statements,
    )


@pytest.mark.asyncio
async def test_risks_list_scopes_a_superuser_to_their_own_tenant():
    from src.api.routes import risks as risks_routes

    db, statements = _capturing_db_with_scalar()

    await risks_routes.list_risks(
        db=db,
        current_user=_superuser(77),
        page=1,
        page_size=20,
        search=None,
        category=None,
        status_filter=None,
        risk_level=None,
        owner_id=None,
    )

    assert len(statements) == 2, "expected the count query and the page query"
    for stmt in statements:
        _assert_exact_tenant_sql(_sql(stmt), 77)


@pytest.mark.asyncio
async def test_risks_list_requires_tenant_for_a_superuser():
    from src.api.routes import risks as risks_routes

    db, statements = _capturing_db_with_scalar()

    with pytest.raises(HTTPException) as exc:
        await risks_routes.list_risks(
            db=db,
            current_user=_superuser(None),
            page=1,
            page_size=20,
            search=None,
            category=None,
            status_filter=None,
            risk_level=None,
            owner_id=None,
        )
    assert exc.value.status_code == 403
    assert not statements, "a tenantless caller must not reach the database"


@pytest.mark.asyncio
async def test_risks_list_ignores_a_superuser_flag_on_every_other_filter():
    """The other query parameters must not reopen the bypass.

    `search`, `category`, `status`, `risk_level` and `owner_id` each append a
    predicate after the tenant filter. Exercising them together pins that none
    of them rebuilds the statement from an unscoped `select(Risk)` — a plausible
    way for the leak to return once the conditional is gone.
    """
    from src.api.routes import risks as risks_routes

    db, statements = _capturing_db_with_scalar()

    await risks_routes.list_risks(
        db=db,
        current_user=_superuser(77),
        page=1,
        page_size=20,
        search="pump",
        category="operational",
        status_filter="open",
        risk_level="high",
        owner_id=5,
    )

    assert len(statements) == 2
    for stmt in statements:
        _assert_exact_tenant_sql(_sql(stmt), 77)


# ---------------------------------------------------------------------------
# The aggregates beside the register (B-13 follow-up to #1513)
#
# `get_risk_statistics` and `get_risk_matrix` kept the bypass #1513 removed from
# `list_risks`, spelled `tf = true()` rather than as a skipped filter call. A
# tenant-bound superuser therefore paged a scoped register and read every
# tenant's totals in the statistics and matrix beside it, so the two surfaces
# answered the same question differently.
#
# Both handlers thread one predicate through several statements, so every
# statement they execute is asserted rather than a nominated one: an eighth
# sub-query added later without the predicate is the way this leak returns.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_risk_statistics_scopes_a_superuser_to_their_own_tenant():
    from src.api.routes import risks as risks_routes

    db, statements = _capturing_db()

    await risks_routes.get_risk_statistics(db=db, current_user=_superuser(77))

    assert len(statements) == 7, "every statistics sub-query must be accounted for"
    for stmt in statements:
        _assert_exact_tenant_sql(_sql(stmt), 77)


@pytest.mark.asyncio
async def test_risk_statistics_requires_tenant_for_a_superuser():
    from src.api.routes import risks as risks_routes

    db, statements = _capturing_db()

    with pytest.raises(HTTPException) as exc:
        await risks_routes.get_risk_statistics(db=db, current_user=_superuser(None))
    assert exc.value.status_code == 403
    assert not statements, "a tenantless caller must not reach the database"


@pytest.mark.asyncio
async def test_risk_matrix_scopes_a_superuser_to_their_own_tenant():
    from src.api.routes import risks as risks_routes

    db, statements = _capturing_db()

    await risks_routes.get_risk_matrix(db=db, current_user=_superuser(77))

    assert len(statements) == 1
    for stmt in statements:
        _assert_exact_tenant_sql(_sql(stmt), 77)


@pytest.mark.asyncio
async def test_risk_matrix_requires_tenant_for_a_superuser():
    from src.api.routes import risks as risks_routes

    db, statements = _capturing_db()

    with pytest.raises(HTTPException) as exc:
        await risks_routes.get_risk_matrix(db=db, current_user=_superuser(None))
    assert exc.value.status_code == 403
    assert not statements, "a tenantless caller must not reach the database"


def test_risk_aggregate_routes_never_branch_on_superuser():
    """Neither aggregate may read `is_superuser` at all.

    The behavioural tests above pin what the current statements do; this pins
    the shape, because the bypass was originally written as `tf = true()` and
    would be just as easy to reintroduce as an unfiltered `select` guarded by a
    fresh conditional. `list_risks` is pinned by
    `test_list_route_tenant_filters_are_never_reached_conditionally` instead —
    it applies the shared helper, which these two cannot, because one predicate
    is reused across several differently-shaped aggregate statements.
    """
    from src.api.routes import risks

    for handler in (risks.get_risk_statistics, risks.get_risk_matrix):
        source = inspect.getsource(handler)
        # Substring rather than AST here: the flag was read two ways across
        # these routes (`current_user.is_superuser` and a `getattr` string),
        # and only one of those is an attribute node.
        assert "is_superuser" not in source, (
            f"{handler.__name__} reads is_superuser; the aggregates must describe "
            "the same population as the register list for every caller"
        )
        tree = ast.parse(source)
        conditional = [node for node in ast.walk(tree) if isinstance(node, ast.If)]
        assert not any(
            "require_tenant_id" in ast.dump(node) for node in conditional
        ), f"{handler.__name__} demands a tenant only on some path"
        assert "require_tenant_id" in ast.dump(tree), f"{handler.__name__} no longer demands a tenant at all"


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
    # This assertion is the one the B-13 documents fix added: the helper used to
    # demand a tenant *and* return the statement unscoped for a superuser, so
    # the `require_tenant_id` check above passed while the library list and the
    # stats panel spanned every tenant.
    assert "is_superuser" not in src

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


def test_list_route_tenant_filters_are_never_reached_conditionally():
    """`apply_tenant_filter` must sit at the top level of these four handlers.

    A behavioural guard alone would let the bypass come back spelled another
    way, so the shape is asserted too. Written against the AST rather than the
    source text because these routes already expressed the same bypass two ways
    (`current_user.is_superuser` and `getattr(current_user, "is_superuser", ...)`),
    and a third spelling would slip past a substring check.

    Only the filter call is pinned, not `require_tenant_id`: the RTA and
    complaint handlers legitimately call that a second time inside the
    `reporter_email` / `complainant_email` branch, to fail closed before writing
    the audit row for an email-targeted search.

    `risks.list_risks` is pinned here rather than in its own test so that the
    set of registers under this rule is one list: a fifth one added later is a
    one-line change here, and forgetting it is visible in the diff.
    """
    from src.api.routes import complaints, near_miss, risks, rtas

    for handler in (near_miss.list_near_misses, rtas.list_rtas, complaints.list_complaints, risks.list_risks):
        tree = ast.parse(inspect.getsource(handler))
        conditional = [node for node in ast.walk(tree) if isinstance(node, ast.If)]
        assert not any(
            "apply_tenant_filter" in ast.dump(node) for node in conditional
        ), f"{handler.__name__} filters by tenant inside a conditional; the register must be scoped for every caller"
        assert "apply_tenant_filter" in ast.dump(tree), f"{handler.__name__} no longer filters by tenant at all"


def test_require_tenant_id_still_403():
    with pytest.raises(HTTPException) as exc:
        require_tenant_id(None)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# The document library (B-13 sibling of the registers above)
#
# `documents._scope_stmt_to_current_tenant` returned the statement unscoped for
# a superuser, so `GET /api/v1/documents/` and `GET /api/v1/documents/stats/
# overview` spanned every tenant — the same defect as the registers, hidden one
# level down in a shared helper rather than written inline in the handler.
#
# The helper now scopes unconditionally and a second, separately named helper
# carries the by-id exemption, so the two capabilities cannot be confused: the
# strict one is what every enumerating and aggregating surface reaches, and the
# lenient one has exactly one caller.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_documents_list_scopes_a_superuser_to_their_own_tenant():
    from src.api.routes import documents as documents_routes

    db, statements = _capturing_db_with_scalar()

    await documents_routes.list_documents(db=db, current_user=_superuser(77), page=1, page_size=20)

    assert len(statements) == 2, "expected the count query and the page query"
    for stmt in statements:
        _assert_exact_tenant_sql(_sql(stmt), 77)


@pytest.mark.asyncio
async def test_documents_list_requires_tenant_for_a_superuser():
    from src.api.routes import documents as documents_routes

    db, statements = _capturing_db_with_scalar()

    with pytest.raises(HTTPException) as exc:
        await documents_routes.list_documents(db=db, current_user=_superuser(None), page=1, page_size=20)
    assert exc.value.status_code == 403
    assert not statements, "a tenantless caller must not reach the database"


@pytest.mark.asyncio
async def test_documents_list_ignores_a_superuser_flag_on_every_filter():
    """The query parameters must not reopen the bypass.

    Each filter appends a predicate after the tenant filter, and `search` adds
    an `OR` group of its own. Exercising them together pins that none of them
    rebuilds the statement from an unscoped `select(Document)`.
    """
    from src.api.routes import documents as documents_routes

    db, statements = _capturing_db_with_scalar()

    await documents_routes.list_documents(
        db=db,
        current_user=_superuser(77),
        page=1,
        page_size=20,
        search="pump",
        document_type="policy",
        category="safety",
        category_id=3,
        site_location_id=4,
        department="hseq",
        status="approved",
        is_indexed=True,
    )

    assert len(statements) == 2
    for stmt in statements:
        _assert_exact_tenant_sql(_sql(stmt), 77)


@pytest.mark.asyncio
async def test_document_stats_scope_a_superuser_to_their_own_tenant():
    """Every sub-query is asserted, not a nominated one.

    The overview builds five statements across two tables (`documents` and
    `document_chunks`); a sixth added later without the helper is the way this
    leak returns.
    """
    from src.api.routes import documents as documents_routes

    db, statements = _capturing_db()

    await documents_routes.get_document_stats(db=db, current_user=_superuser(77))

    assert len(statements) == 5, "every stats sub-query must be accounted for"
    for stmt in statements:
        _assert_exact_tenant_sql(_sql(stmt), 77)


@pytest.mark.asyncio
async def test_document_stats_require_tenant_for_a_superuser():
    from src.api.routes import documents as documents_routes

    db, statements = _capturing_db()

    with pytest.raises(HTTPException) as exc:
        await documents_routes.get_document_stats(db=db, current_user=_superuser(None))
    assert exc.value.status_code == 403
    assert not statements, "a tenantless caller must not reach the database"


@pytest.mark.asyncio
async def test_documents_by_id_lookup_keeps_the_superuser_exemption():
    """The capability this change must NOT take away.

    Withdrawing enumeration while leaving single-record administration intact is
    the whole shape of B-13. Without this test a later tidy-up that pointed
    `_get_document_or_404` at the strict helper would look like an improvement.
    """
    from src.api.routes import documents as documents_routes

    statements: list = []
    document = SimpleNamespace(id=5, tenant_id=999, access_level=None, category_id=None)

    async def execute(statement):
        statements.append(statement)
        return SimpleNamespace(scalar_one_or_none=lambda: document)

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))

    loaded = await documents_routes._get_document_or_404(db, 5, _superuser(77))

    assert loaded is document
    # The selected column list names TENANT_ID on every row, so only the
    # predicate is examined.
    where = " ".join(_sql(statements[0]).split()).split(" WHERE ", 1)[1]
    assert "TENANT_ID" not in where, "a superuser must still reach one document in any tenant by id"


def test_documents_tenant_scope_helper_never_branches_on_a_superuser():
    """Pin the shape as well as the behaviour.

    The bypass lived in this helper for every caller at once, so a conditional
    reappearing here is worth catching directly rather than only through the
    handlers that happen to be exercised above. Asserted two ways because the
    flag is read as an attribute in some routes and through a `getattr` string
    in others, and only one of those is an attribute node.
    """
    from src.api.routes import documents

    source = inspect.getsource(documents._scope_stmt_to_current_tenant)
    assert "is_superuser" not in source
    tree = ast.parse(source)
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.If)]
    assert "require_tenant_id" in ast.dump(tree)

    # The exemption is allowed to exist, but only where it is named as one.
    lenient = inspect.getsource(documents._scope_stmt_to_tenant_unless_superuser)
    assert "is_superuser" in lenient
    by_id = inspect.getsource(documents._get_document_or_404)
    assert "_scope_stmt_to_tenant_unless_superuser" in by_id
