"""Authoring copilot knowledge is a publishing act, so it needs more than a session.

Entries created through ``POST /copilot/knowledge`` are what ``/knowledge/search``
returns, and they are read back to everyone in the tenant with the assistant's voice
behind them. While the route took only ``CurrentUser``, any authenticated account could
put words in the copilot's mouth for the whole organisation.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_current_user
from src.api.routes import copilot as copilot_routes
from src.core.config import settings
from src.domain.services.copilot_kill_switch import reset_copilot_kill_switch_cache

COPILOT_PREFIX = "/api/v1/copilot"
KNOWLEDGE_QUERY = "?title=Site+rule&content=Hard+hats+required&category=safety"
REQUIRED_PERMISSION = "admin:manage"


class _FakeSessionFactory:
    """No-op kill-switch read, so these tests exercise authorisation and nothing else."""

    def __call__(self) -> "_FakeSessionFactory":
        return self

    async def __aenter__(self) -> "_FakeSessionFactory":
        return self

    async def __aexit__(self, *_exc_info: object) -> bool:
        return False

    async def execute(self, _statement: object) -> "_FakeSessionFactory":
        return self

    def scalar_one_or_none(self) -> None:
        return None


def _caller(*permissions: str) -> SimpleNamespace:
    granted = set(permissions)
    return SimpleNamespace(
        id=1,
        email="qhse@example.com",
        tenant_id=1,
        is_active=True,
        is_superuser=False,
        has_permission=lambda permission: permission in granted,
    )


@pytest.fixture(autouse=True)
def copilot_open(monkeypatch, app):
    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(copilot_routes, "async_session_maker", _FakeSessionFactory())
    reset_copilot_kill_switch_cache()
    yield
    reset_copilot_kill_switch_cache()


@pytest.fixture
def as_caller(app):
    def _install(user: SimpleNamespace):
        async def _current_user():
            return user

        app.dependency_overrides[get_current_user] = _current_user

    try:
        yield _install
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_an_ordinary_authenticated_user_cannot_author_knowledge(client: TestClient, as_caller):
    as_caller(_caller("incident:create", "risk:read"))

    response = client.post(f"{COPILOT_PREFIX}/knowledge{KNOWLEDGE_QUERY}")

    assert response.status_code == 403
    assert REQUIRED_PERMISSION in response.text


def test_a_caller_holding_the_permission_reaches_the_handler(client: TestClient, as_caller, monkeypatch):
    """The gate must admit the intended role, not merely refuse everyone."""
    from src.domain.services.copilot_service import CopilotService

    async def _add_knowledge(self, **kwargs):
        return SimpleNamespace(id=7, title=kwargs["title"])

    monkeypatch.setattr(CopilotService, "add_knowledge", _add_knowledge)
    as_caller(_caller(REQUIRED_PERMISSION))

    response = client.post(f"{COPILOT_PREFIX}/knowledge{KNOWLEDGE_QUERY}")

    assert response.status_code == 200, response.text
    assert response.json() == {"id": 7, "title": "Site rule"}


def test_reading_knowledge_stays_open_to_any_authenticated_user(client: TestClient, as_caller, monkeypatch):
    """Only authoring is being restricted; the search side is unchanged."""
    from src.domain.services.copilot_service import CopilotService

    async def _search_knowledge(self, **kwargs):
        return []

    monkeypatch.setattr(CopilotService, "search_knowledge", _search_knowledge)
    as_caller(_caller("incident:create"))

    response = client.get(f"{COPILOT_PREFIX}/knowledge/search", params={"query": "capa"})

    assert response.status_code == 200
    assert response.json() == []


def test_the_disabled_copilot_still_hides_the_route_from_a_permitted_caller(client: TestClient, as_caller, monkeypatch):
    """The feature gate stays ahead of the permission gate: 404, not 403.

    A 403 would confirm the endpoint exists in an environment that has not opted in.
    """
    monkeypatch.setattr(settings, "ai_copilot_enabled", False)
    as_caller(_caller(REQUIRED_PERMISSION))

    assert client.post(f"{COPILOT_PREFIX}/knowledge{KNOWLEDGE_QUERY}").status_code == 404
