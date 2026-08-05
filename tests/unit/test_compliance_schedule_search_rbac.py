"""Global Search registration for Compliance Schedule, and its fail-closed RBAC.

The rest of ``SearchService`` filters by tenant alone. This module must not: an
obligation register is only visible to a caller holding ``compliance_schedule:read``,
so search cannot become a side door onto records the register itself would refuse.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from src.domain.services import search_service as search_service_module
from src.domain.services.search_interpret_service import ALLOWED_MODULES
from src.domain.services.search_service import COMPLIANCE_SCHEDULE_MODULE, PERM_COMPLIANCE_SCHEDULE_READ, SearchService

TENANT_ID = 17


def _sql_with_params(statement) -> tuple[str, dict]:
    compiled = statement.compile(dialect=postgresql.dialect())
    params = {str(k).lower(): v for k, v in compiled.params.items()}
    return str(compiled).lower(), params


def _user(*, tenant_id: int | None = TENANT_ID, perms: set[str] | None = None, is_superuser: bool = False):
    allowed = set(perms or ())
    return SimpleNamespace(
        id=1,
        tenant_id=tenant_id,
        is_superuser=is_superuser,
        has_permission=lambda p: p in allowed,
    )


def _requirement(
    *,
    requirement_id: int = 5,
    reference_number: str | None = "CSR-2026-0001",
    title: str | None = "Fire Risk Assessment",
    description: str | None = "Annual FRA for the Wickford depot",
    next_due_date: date | None = None,
):
    return SimpleNamespace(
        id=requirement_id,
        reference_number=reference_number,
        title=title,
        description=description,
        next_due_date=next_due_date or (date.today() + timedelta(days=365)),
    )


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


def _db(rows=None, *, capture: list | None = None):
    async def execute(statement):
        if capture is not None:
            capture.append(statement)
        return _ScalarResult(rows or [])

    return SimpleNamespace(execute=AsyncMock(side_effect=execute))


@pytest.fixture(autouse=True)
def module_open(monkeypatch):
    """Default every test to an environment where the module is switched on."""
    monkeypatch.setattr(search_service_module.settings, "compliance_schedule_enabled", True)
    monkeypatch.setattr(
        search_service_module,
        "compliance_schedule_kill_switch_last_known",
        lambda: False,
    )


# ---------------------------------------------------------------------------
# Fail-closed gates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_without_compliance_schedule_read_no_query_is_issued():
    db = _db()
    service = SearchService(db)
    user = _user(perms=set())  # authenticated, but not on the register

    hits = await service._search_compliance_requirements("fire", TENANT_ID, "r1", user=user)

    assert hits == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_a_neighbouring_permission_does_not_admit():
    """Holding some other module's read must not open this one."""
    db = _db([_requirement()])
    service = SearchService(db)
    user = _user(perms={"document:read", "incident:read"})

    hits = await service._search_compliance_requirements("fire", TENANT_ID, "r1", user=user)

    assert hits == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_anonymous_caller_is_refused():
    db = _db([_requirement()])
    hits = await SearchService(db)._search_compliance_requirements("fire", TENANT_ID, "r1", user=None)

    assert hits == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_absent_tenant_scope_is_refused():
    db = _db([_requirement()])
    user = _user(tenant_id=None, perms={PERM_COMPLIANCE_SCHEDULE_READ})

    hits = await SearchService(db)._search_compliance_requirements("fire", None, "r1", user=user)

    assert hits == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_caller_tenancy_must_agree_with_the_scope_asked_for():
    """A permitted user still cannot be pointed at another tenant's register."""
    db = _db([_requirement()])
    user = _user(tenant_id=99, perms={PERM_COMPLIANCE_SCHEDULE_READ})

    hits = await SearchService(db)._search_compliance_requirements("fire", TENANT_ID, "r1", user=user)

    assert hits == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_module_disabled_in_this_environment_returns_nothing(monkeypatch):
    monkeypatch.setattr(search_service_module.settings, "compliance_schedule_enabled", False)
    db = _db([_requirement()])
    user = _user(perms={PERM_COMPLIANCE_SCHEDULE_READ})

    hits = await SearchService(db)._search_compliance_requirements("fire", TENANT_ID, "r1", user=user)

    assert hits == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_observed_kill_switch_closes_search_too(monkeypatch):
    monkeypatch.setattr(
        search_service_module,
        "compliance_schedule_kill_switch_last_known",
        lambda: True,
    )
    db = _db([_requirement()])
    user = _user(perms={PERM_COMPLIANCE_SCHEDULE_READ})

    hits = await SearchService(db)._search_compliance_requirements("fire", TENANT_ID, "r1", user=user)

    assert hits == []
    db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Admitted callers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_permitted_caller_gets_the_obligation():
    requirement = _requirement()
    db = _db([requirement])
    user = _user(perms={PERM_COMPLIANCE_SCHEDULE_READ})

    hits = await SearchService(db)._search_compliance_requirements("fire", TENANT_ID, "r1", user=user)

    assert len(hits) == 1
    hit = hits[0]
    assert hit.id == "CSR-2026-0001"
    assert hit.type == "compliance_requirement"
    assert hit.module == COMPLIANCE_SCHEDULE_MODULE
    assert hit.title == "Fire Risk Assessment"
    assert hit.path == "/compliance-schedule/5"
    assert hit.entity_id == 5


@pytest.mark.asyncio
async def test_superuser_is_admitted_without_an_explicit_grant():
    db = _db([_requirement()])
    user = _user(perms=set(), is_superuser=True)

    hits = await SearchService(db)._search_compliance_requirements("fire", TENANT_ID, "r1", user=user)

    assert len(hits) == 1


@pytest.mark.asyncio
async def test_status_reflects_the_due_date_not_a_stored_column():
    overdue = _requirement(requirement_id=1, next_due_date=date.today() - timedelta(days=1))
    due_soon = _requirement(requirement_id=2, next_due_date=date.today() + timedelta(days=5))
    current = _requirement(requirement_id=3, next_due_date=date.today() + timedelta(days=200))
    user = _user(perms={PERM_COMPLIANCE_SCHEDULE_READ})

    statuses = []
    for requirement in (overdue, due_soon, current):
        hits = await SearchService(_db([requirement]))._search_compliance_requirements(
            "fire", TENANT_ID, "r1", user=user
        )
        statuses.append(hits[0].status)

    assert statuses == ["overdue", "due_soon", "current"]


@pytest.mark.asyncio
async def test_reference_falls_back_when_the_row_has_none():
    db = _db([_requirement(reference_number=None)])
    user = _user(perms={PERM_COMPLIANCE_SCHEDULE_READ})

    hits = await SearchService(db)._search_compliance_requirements("fire", TENANT_ID, "r1", user=user)

    assert hits[0].id == "CSR-5"


@pytest.mark.asyncio
async def test_empty_register_yields_no_hits_and_does_not_raise():
    db = _db([])
    user = _user(perms={PERM_COMPLIANCE_SCHEDULE_READ})

    hits = await SearchService(db)._search_compliance_requirements("fire", TENANT_ID, "r1", user=user)

    assert hits == []
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_failing_query_degrades_to_no_hits_rather_than_a_500():
    from sqlalchemy.exc import SQLAlchemyError

    db = SimpleNamespace(execute=AsyncMock(side_effect=SQLAlchemyError("boom")))
    user = _user(perms={PERM_COMPLIANCE_SCHEDULE_READ})

    hits = await SearchService(db)._search_compliance_requirements("fire", TENANT_ID, "r1", user=user)

    assert hits == []


# ---------------------------------------------------------------------------
# The SQL itself
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sql_scopes_tenant_and_excludes_retired_and_deleted_rows():
    statements: list = []
    db = _db([], capture=statements)
    user = _user(perms={PERM_COMPLIANCE_SCHEDULE_READ})

    await SearchService(db)._search_compliance_requirements("fire drill", TENANT_ID, "r1", user=user)

    assert len(statements) == 1
    sql, params = _sql_with_params(statements[0])
    assert "compliance_requirements" in sql
    assert "compliance_requirements.tenant_id = " in sql
    assert TENANT_ID in params.values()
    # Predicate forms, not bare column names: ``select(ComplianceRequirement)`` puts
    # every column in the SELECT list, so "is_active" appears whether it is filtered
    # on or not. Asserting the name alone passed against a build with no filter.
    assert "compliance_requirements.deleted_at is null" in sql
    assert "compliance_requirements.is_active is true" in sql
    assert "%fire drill%" in params.values()
    # Title, description and reference are all reachable.
    assert sql.count("ilike") == 3


# ---------------------------------------------------------------------------
# Registration in the wider search surface
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_dispatch_includes_compliance_results_and_facets():
    db = _db([_requirement()])
    service = SearchService(db)
    user = _user(perms={PERM_COMPLIANCE_SCHEDULE_READ})

    for method in (
        "_search_incidents",
        "_search_near_misses",
        "_search_rtas",
        "_search_complaints",
        "_search_risks",
        "_search_audits",
        "_search_actions",
        "_search_documents",
        "_search_document_content",
    ):
        setattr(service, method, AsyncMock(return_value=[]))

    with patch("src.domain.services.search_service.track_metric"):
        result = await service.search(query="fire", tenant_id=TENANT_ID, user=user)

    assert result["total"] == 1
    assert result["facets"]["modules"][COMPLIANCE_SCHEDULE_MODULE] == 1
    assert result["results"][0]["path"] == "/compliance-schedule/5"


@pytest.mark.asyncio
async def test_search_dispatch_hides_compliance_from_an_unpermitted_caller():
    db = _db([_requirement()])
    service = SearchService(db)
    user = _user(perms={"document:read"})

    for method in (
        "_search_incidents",
        "_search_near_misses",
        "_search_rtas",
        "_search_complaints",
        "_search_risks",
        "_search_audits",
        "_search_actions",
        "_search_documents",
        "_search_document_content",
    ):
        setattr(service, method, AsyncMock(return_value=[]))

    with patch("src.domain.services.search_service.track_metric"):
        result = await service.search(query="fire", tenant_id=TENANT_ID, user=user)

    assert result["total"] == 0
    assert COMPLIANCE_SCHEDULE_MODULE not in result["facets"]["modules"]


@pytest.mark.asyncio
async def test_module_filter_selects_compliance_hits():
    db = _db([_requirement()])
    service = SearchService(db)
    user = _user(perms={PERM_COMPLIANCE_SCHEDULE_READ})

    for method in (
        "_search_incidents",
        "_search_near_misses",
        "_search_rtas",
        "_search_complaints",
        "_search_risks",
        "_search_audits",
        "_search_actions",
        "_search_documents",
        "_search_document_content",
    ):
        setattr(service, method, AsyncMock(return_value=[]))

    with patch("src.domain.services.search_service.track_metric"):
        result = await service.search(
            query="fire",
            tenant_id=TENANT_ID,
            user=user,
            module=COMPLIANCE_SCHEDULE_MODULE,
        )

    assert result["total"] == 1


def test_interpret_allows_the_module_so_a_filter_survives_validation():
    from src.domain.services.search_interpret_service import validate_intent

    assert COMPLIANCE_SCHEDULE_MODULE in ALLOWED_MODULES
    intent = validate_intent({"q": "fra", "module": COMPLIANCE_SCHEDULE_MODULE}, fallback_q="fra")
    assert intent["module"] == COMPLIANCE_SCHEDULE_MODULE
