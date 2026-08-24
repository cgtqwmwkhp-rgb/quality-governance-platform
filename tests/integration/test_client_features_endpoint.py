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
from sqlalchemy import delete

from src.core.config import settings
from src.domain.features.evaluator import reset_client_feature_cache
from src.domain.models.feature_flag import FeatureFlag
from src.domain.services.compliance_schedule_kill_switch import reset_compliance_schedule_kill_switch_cache
from src.domain.services.copilot_kill_switch import reset_copilot_kill_switch_cache
from src.domain.services.feature_flag_service import FeatureFlagService

ENDPOINT = "/api/v1/meta/features"


def _reset_every_flag_cache() -> None:
    """Clear every cache that reads the ``feature_flags`` table.

    ``FeatureFlagService`` is included even though this endpoint does not use it:
    its module-level cache has no TTL and holds ORM instances, so a row this
    module writes would otherwise be served to a later test from a closed
    session, which surfaces as DetachedInstanceError somewhere unrelated.
    """
    reset_client_feature_cache()
    reset_compliance_schedule_kill_switch_cache()
    reset_copilot_kill_switch_cache()
    FeatureFlagService.clear_cache()


@pytest.fixture(autouse=True)
def _clean_flag_caches():
    _reset_every_flag_cache()
    yield
    _reset_every_flag_cache()


@pytest.fixture
async def flag_row(test_session):
    """Insert ``feature_flags`` rows and guarantee they are gone afterwards.

    The integration database is shared, so a committed row outlives the test that
    wrote it. Leaving one behind here would silently disable Compliance Schedule
    or user management for every test that ran later.
    """
    created: list[str] = []

    async def _add(key: str, *, enabled: bool) -> None:
        test_session.add(FeatureFlag(key=key, name=key, enabled=enabled))
        await test_session.commit()
        created.append(key)
        _reset_every_flag_cache()

    yield _add

    for key in created:
        await test_session.execute(delete(FeatureFlag).where(FeatureFlag.key == key))
    await test_session.commit()
    _reset_every_flag_cache()


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


@pytest.fixture
def copilot_settings(monkeypatch):
    """Set both copilot openers, clearing the kill-switch cache around the change.

    The copilot switch keeps its verdict for 30s in a module global, so a test that
    engages the kill would otherwise close the copilot for whatever ran next.
    """

    def _set(*, surface: bool, inference: bool):
        monkeypatch.setattr(settings, "ai_copilot_enabled", surface)
        monkeypatch.setattr(settings, "ai_copilot_inference_enabled", inference)
        reset_copilot_kill_switch_cache()

    return _set


@pytest.fixture
def copilot_off(copilot_settings):
    copilot_settings(surface=False, inference=False)
    yield
    reset_copilot_kill_switch_cache()


@pytest.fixture
def copilot_on(copilot_settings):
    copilot_settings(surface=True, inference=False)
    yield
    reset_copilot_kill_switch_cache()


@pytest.fixture
def copilot_inference_on(copilot_settings):
    copilot_settings(surface=True, inference=True)
    yield
    reset_copilot_kill_switch_cache()


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


async def test_kill_switch_closes_the_feature(superuser_client: AsyncClient, compliance_schedule_on, flag_row):
    """Engaging the switch must hide the nav, not merely 404 the API behind it."""
    await flag_row("compliance_schedule_kill_switch", enabled=True)

    flags = (await superuser_client.get(ENDPOINT)).json()["flags"]
    assert flags["compliance_schedule"] is False


async def test_copilot_pair_is_published(unauth_client: AsyncClient, copilot_off):
    """The panel reads both halves; a missing key would send it back to a hardcoded claim."""
    flags = (await unauth_client.get(ENDPOINT)).json()["flags"]
    assert flags["ai_copilot"] is False
    assert flags["ai_copilot_inference"] is False


async def test_copilot_open_without_inference(unauth_client: AsyncClient, copilot_on):
    """Surface open, inference off — the keyword simulator, and the panel must say so."""
    flags = (await unauth_client.get(ENDPOINT)).json()["flags"]
    assert flags["ai_copilot"] is True
    assert flags["ai_copilot_inference"] is False


async def test_copilot_inference_open_when_both_configured(unauth_client: AsyncClient, copilot_inference_on):
    """Grounded answers really are phrased by a model, so the flag has to admit it."""
    flags = (await unauth_client.get(ENDPOINT)).json()["flags"]
    assert flags["ai_copilot"] is True
    assert flags["ai_copilot_inference"] is True


async def test_copilot_kill_switch_closes_both(unauth_client: AsyncClient, copilot_inference_on, flag_row):
    """Engaging the kill must withdraw the grounded claim, not only 404 the API."""
    await flag_row("copilot_kill_switch", enabled=True)

    flags = (await unauth_client.get(ENDPOINT)).json()["flags"]
    assert flags["ai_copilot"] is False
    assert flags["ai_copilot_inference"] is False


async def test_admin_user_management_defaults_open(unauth_client: AsyncClient):
    """No row means open, matching _ensure_user_management_enabled."""
    flags = (await unauth_client.get(ENDPOINT)).json()["flags"]
    assert flags["admin_user_management"] is True


async def test_disabling_row_closes_admin_user_management(unauth_client: AsyncClient, flag_row):
    """A positive flag reads the opposite way round from a kill switch."""
    await flag_row("admin_user_management", enabled=False)

    flags = (await unauth_client.get(ENDPOINT)).json()["flags"]
    assert flags["admin_user_management"] is False
