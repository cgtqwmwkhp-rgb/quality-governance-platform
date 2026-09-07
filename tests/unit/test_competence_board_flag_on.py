"""CB-PR6: the competence board ships open, and false still subtracts.

CB-PR1–PR5 all shipped behind ``competence_board_enabled`` default false. This
slice flips that default and records ADR-0026. What has to stay true afterwards
is the part worth testing: the flag is still a *kill* rather than a decoration,
both of its names still reach the field, and flag-on opened exactly the ten
routes that already existed and nothing else.

The 404s are asserted through a real request against the real router rather than
by reading the dependency list, because "the dependency is attached" and "a
closed flag returns 404 before auth, tenant or database resolution" are two
different claims and only the second one is the kill switch.

The no-PAMS-write half of ADR-0026 is enforced where it can actually be
observed, not here: ``test_competence_assessment_overlay.py`` explodes on any
attempt to build a PAMS engine or fetch PAMS rows from an assessment path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import AliasChoices

from src.api.routes import workforce_competence_board as board_routes
from src.core.config import Settings, settings

ADR_PATH = Path(__file__).resolve().parents[2] / "docs/adr/ADR-0026-competence-issued-vs-demonstrated.md"

#: Declared order matters — pydantic resolves ``AliasChoices`` first-match-wins.
ALIAS_NAMES = (
    "COMPETENCE_BOARD_ENABLED",
    "FF_COMPETENCE_BOARD",
    "competence_board_enabled",
)

#: Every path/method declared on the flagged router, as an operator would call it.
GUARDED_REQUESTS = (
    ("GET", "/board"),
    ("GET", "/change-requests"),
    ("POST", "/change-requests"),
    ("GET", "/assessment-binds"),
    ("POST", "/assessment-binds"),
    ("DELETE", "/assessment-binds/1"),
    # CB-UI-3. The one write on this router that creates a run, so the kill
    # switch closing it matters more here than anywhere else on the board.
    ("POST", "/assessments"),
    ("GET", "/coverage"),
    ("GET", "/coverage-quotas"),
    ("POST", "/coverage-quotas"),
    ("DELETE", "/coverage-quotas/1"),
)


def _iter_api_routes(router):
    """Flatten ``include_router`` mounts.

    FastAPI >=0.140 (the lockfile pin) wraps included routers as
    ``_IncludedRouter`` with no ``.path``. Child routes live on
    ``original_router``. Older FastAPI flattens APIRoutes onto the parent.
    """
    for route in getattr(router, "routes", []) or []:
        nested_router = getattr(route, "original_router", None)
        if nested_router is not None:
            yield from _iter_api_routes(nested_router)
            continue
        nested = getattr(route, "routes", None)
        if nested is not None:
            yield from _iter_api_routes(route)
            continue
        yield route


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(board_routes.router, prefix="/api/v1/workforce/competence")
    return TestClient(app)


# ----------------------------------------------------------------- the default


def test_flag_default_is_on():
    """Asserted on the field default, not the live instance.

    An ambient ``COMPETENCE_BOARD_ENABLED`` in the shell or CI environment would
    otherwise decide this test, which is not what the ADR decided.
    """
    assert Settings.model_fields["competence_board_enabled"].default is True


def test_both_kill_switch_names_still_reach_the_field():
    """ADR-0026 promises operators two names. A dropped alias is a dead kill switch."""
    alias = Settings.model_fields["competence_board_enabled"].validation_alias
    assert isinstance(alias, AliasChoices)
    assert tuple(alias.choices) == ALIAS_NAMES


@pytest.mark.parametrize("env_name", ALIAS_NAMES)
def test_each_env_name_can_still_close_the_open_default(monkeypatch, env_name):
    """The default being on is only safe if the environment can still close it.

    Every alias is cleared first: pydantic resolves ``AliasChoices`` in order, so
    an ambient ``COMPETENCE_BOARD_ENABLED`` in the shell or on a CI runner would
    otherwise shadow the ``FF_`` case and make this test a report on the machine
    rather than on the field.
    """
    for name in ALIAS_NAMES:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv(env_name, "false")
    assert Settings().competence_board_enabled is False

    monkeypatch.setenv(env_name, "true")
    assert Settings().competence_board_enabled is True


# ------------------------------------------------------- the kill still kills


@pytest.mark.parametrize("method,path", GUARDED_REQUESTS, ids=lambda value: str(value).lstrip("/"))
def test_every_guarded_route_is_404_while_the_flag_is_closed(monkeypatch, method, path):
    """404 must also be the *first* verdict.

    None of these requests carry a token and none can open a database session,
    so a 401, 403 or 500 here would mean the flag is consulted after something
    that fails differently — and a closed board would leak that it exists.
    """
    monkeypatch.setattr(settings, "competence_board_enabled", False)
    response = _client().request(method, f"/api/v1/workforce/competence{path}", json={})

    assert response.status_code == 404, f"{method} {path} answered {response.status_code} with the flag closed"
    assert response.json()["detail"] == board_routes.DISABLED_DETAIL


@pytest.mark.asyncio
async def test_open_flag_lets_the_dependency_through(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    assert await board_routes.require_competence_board_enabled() is None


# ------------------------------------------------- registration, not invention


def test_the_flagged_router_carries_exactly_the_expected_routes():
    """Flag-on is the API. Anything else appearing here is a surface nobody locked."""
    assert any(
        getattr(dependency, "dependency", None) is board_routes.require_competence_board_enabled
        for dependency in board_routes._enabled_router.dependencies
    )
    registered = {
        (method, route.path)
        for route in _iter_api_routes(board_routes._enabled_router)
        for method in sorted(route.methods)
    }
    assert registered == {
        ("GET", "/board"),
        ("GET", "/change-requests"),
        ("POST", "/change-requests"),
        ("GET", "/assessment-binds"),
        ("POST", "/assessment-binds"),
        ("DELETE", "/assessment-binds/{bind_id}"),
        ("POST", "/assessments"),
        ("GET", "/coverage"),
        ("GET", "/coverage-quotas"),
        ("POST", "/coverage-quotas"),
        ("DELETE", "/coverage-quotas/{quota_id}"),
    }


# ------------------------------------------------------------------- ADR-0026


def test_adr_0026_exists_and_is_accepted():
    text = ADR_PATH.read_text(encoding="utf-8")
    assert "**Status**: Accepted" in text
    assert "**Date**: 2026-09-02" in text
    assert "**Decision Makers**:" in text


def test_adr_0026_states_the_three_facts_and_the_pams_abstention():
    text = ADR_PATH.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "issued is pams's fact" in lowered
    assert "demonstrated is qgp's fact" in lowered
    assert "statutory is citation's fact" in lowered
    assert "never issues an insert, update or delete against a pams" in lowered
    assert "a pass writes nothing to pams" in lowered
    assert "adr-0020" in lowered
    assert "competencydashboard" in lowered


def test_adr_0026_records_the_subtract_only_kill():
    lowered = ADR_PATH.read_text(encoding="utf-8").lower()

    assert "default on" in lowered
    assert "competence_board_enabled=false" in lowered
    assert "subtract-only kill" in lowered
    assert "404" in lowered


def test_env_example_documents_the_open_default():
    """A flag whose default changed silently is a flag an operator cannot find."""
    env_example = (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8")
    assert "COMPETENCE_BOARD_ENABLED=true" in env_example
