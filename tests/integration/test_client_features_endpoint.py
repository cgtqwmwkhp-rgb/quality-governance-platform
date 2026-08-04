"""GET /api/v1/meta/features — the channel the frontend uses instead of guessing.

The properties worth protecting here are the ones a browser depends on: that the
endpoint answers without credentials rather than 401ing on the first call of a
session, that a feature is reported open only when the API would actually serve
it, and that permission-gated features are never reported open to a caller who
could not use them.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.core.config import settings
from src.domain.features.evaluator import reset_client_feature_cache
from src.domain.services.compliance_schedule_kill_switch import reset_compliance_schedule_kill_switch_cache

ENDPOINT = "/api/v1/meta/features"


@pytest.fixture(autouse=True)
def _clean_flag_caches():
    reset_client_feature_cache()
    reset_compliance_schedule_kill_switch_cache()
    yield
    reset_client_feature_cache()
    reset_compliance_schedule_kill_switch_cache()


@pytest.fixture
def compliance_schedule_on(monkeypatch):
    monkeypatch.setattr(settings, "compliance_schedule_enabled", True)
    reset_compliance_schedule_kill_switch_cache()
    yield
    reset_compliance_schedule_kill_switch_cache()


@pytest.fixture
def compliance_schedule_off(monkeypatch):
    monkeypatch.setattr(settings, "compliance_schedule_enabled", False)
    reset_compliance_schedule_kill_switch_cache()
    yield
    reset_compliance_schedule_kill_switch_cache()


async def test_anonymous_caller_gets_200_and_never_401(unauth_client: AsyncClient):
    """A 401 here would make the first call of every session race token refresh."""
    response = await unauth_client.get(ENDPOINT)
    assert response.status_code == 200, response.text
    assert response.json()["scope"] == "anonymous"


async def test_response_shape(unauth_client: AsyncClient):
    body = (await unauth_client.get(ENDPOINT)).json()
    assert set(body) == {"flags", "scope", "evaluated_at", "ttl_seconds"}
    assert isinstance(body["flags"], dict)
    assert all(isinstance(v, bool) for v in body["flags"].values())
    assert body["ttl_seconds"] > 0


async def test_registered_features_are_all_present(unauth_client: AsyncClient):
    """A missing key would make the client fall back to its default and diverge."""
    from src.domain.features.catalogue import CLIENT_FEATURE_KEYS

    flags = (await unauth_client.get(ENDPOINT)).json()["flags"]
    assert set(flags) == set(CLIENT_FEATURE_KEYS)


async def test_permission_gated_feature_is_false_for_anonymous(unauth_client: AsyncClient, compliance_schedule_on):
    """Even with the setting on, nobody unauthenticated can use it, so it reads false."""
    flags = (await unauth_client.get(ENDPOINT)).json()["flags"]
    assert flags["compliance_schedule"] is False


async def test_config_off_reports_false_even_for_superuser(superuser_client: AsyncClient, compliance_schedule_off):
    """The configuration opener is checked before anything else, as the router does."""
    body = (await superuser_client.get(ENDPOINT)).json()
    assert body["scope"] == "user"
    assert body["flags"]["compliance_schedule"] is False


async def test_config_on_reports_true_for_superuser(superuser_client: AsyncClient, compliance_schedule_on):
    """has_permission short-circuits true for superusers, so the fold cannot hide it."""
    flags = (await superuser_client.get(ENDPOINT)).json()["flags"]
    assert flags["compliance_schedule"] is True


async def test_kill_switch_closes_the_feature(superuser_client: AsyncClient, compliance_schedule_on, test_session):
    """Engaging the switch must hide the nav, not merely 404 the API behind it."""
    from src.domain.models.feature_flag import FeatureFlag

    test_session.add(
        FeatureFlag(
            key="compliance_schedule_kill_switch",
            name="Compliance Schedule kill switch",
            enabled=True,
        )
    )
    await test_session.commit()
    reset_compliance_schedule_kill_switch_cache()

    flags = (await superuser_client.get(ENDPOINT)).json()["flags"]
    assert flags["compliance_schedule"] is False


async def test_admin_user_management_defaults_open(unauth_client: AsyncClient):
    """No row means open, matching _ensure_user_management_enabled."""
    flags = (await unauth_client.get(ENDPOINT)).json()["flags"]
    assert flags["admin_user_management"] is True


async def test_disabling_row_closes_admin_user_management(unauth_client: AsyncClient, test_session):
    """A positive flag reads the opposite way round from a kill switch."""
    from src.domain.models.feature_flag import FeatureFlag

    test_session.add(FeatureFlag(key="admin_user_management", name="User management", enabled=False))
    await test_session.commit()
    reset_client_feature_cache()

    flags = (await unauth_client.get(ENDPOINT)).json()["flags"]
    assert flags["admin_user_management"] is False
