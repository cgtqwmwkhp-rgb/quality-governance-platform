"""What ``GET /api/v1/meta/features`` says about the copilot, evaluated in isolation.

The copilot panel used to hardcode "Demonstration only — no AI model is involved"
in every environment, including ones where ``AI_COPILOT_INFERENCE_ENABLED`` was on
and answers really were phrased by a model over register facts. These two flags are
what let the panel stop guessing, so the property worth protecting is that they are
never open when the copilot is not: a UI that overstates what it is doing is the
defect this pair exists to remove, and it can only overstate if a flag does first.

No database here. The feature-flag reads go through a stub session factory, so the
gate arithmetic is asserted without an integration fixture; the endpoint-level pass
lives in ``tests/integration/test_client_features_endpoint.py``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

import pytest

from src.core.config import settings
from src.domain.features.evaluator import evaluate_client_features, reset_client_feature_cache
from src.domain.services.copilot_kill_switch import reset_copilot_kill_switch_cache


class _StubResult:
    def __init__(self, scalar: Optional[bool]) -> None:
        self._scalar = scalar

    def scalar_one_or_none(self) -> Optional[bool]:
        return self._scalar


class _StubSession:
    """Answers every ``feature_flags`` lookup with the same row value."""

    def __init__(self, scalar: Optional[bool]) -> None:
        self._scalar = scalar

    async def execute(self, *_args, **_kwargs) -> _StubResult:
        return _StubResult(self._scalar)


def _session_factory(flag_row: Optional[bool] = None):
    """A session factory whose single row stands in for the whole table.

    ``None`` means no row exists, which is the shipped state: no kill engaged.
    """

    @asynccontextmanager
    async def factory():
        yield _StubSession(flag_row)

    return factory


@pytest.fixture(autouse=True)
def _clear_caches():
    """Both caches hold verdicts for 30s, which would leak across these tests."""
    reset_client_feature_cache()
    reset_copilot_kill_switch_cache()
    yield
    reset_client_feature_cache()
    reset_copilot_kill_switch_cache()


@pytest.fixture
def copilot_settings(monkeypatch):
    def _set(*, surface: bool, inference: bool) -> None:
        monkeypatch.setattr(settings, "ai_copilot_enabled", surface)
        monkeypatch.setattr(settings, "ai_copilot_inference_enabled", inference)

    return _set


async def test_both_closed_when_configuration_says_nothing(copilot_settings):
    """The shipped default. The panel must be able to say 'unavailable' from this."""
    copilot_settings(surface=False, inference=False)

    flags = await evaluate_client_features(None, _session_factory())

    assert flags["ai_copilot"] is False
    assert flags["ai_copilot_inference"] is False


async def test_surface_open_without_inference_is_the_simulator(copilot_settings):
    """This is the state the old hardcoded 'no AI model' banner described correctly."""
    copilot_settings(surface=True, inference=False)

    flags = await evaluate_client_features(None, _session_factory())

    assert flags["ai_copilot"] is True
    assert flags["ai_copilot_inference"] is False


async def test_both_open_when_inference_is_configured_on(copilot_settings):
    """The state the panel used to misdescribe: a model does phrase the answer."""
    copilot_settings(surface=True, inference=True)

    flags = await evaluate_client_features(None, _session_factory())

    assert flags["ai_copilot"] is True
    assert flags["ai_copilot_inference"] is True


async def test_inference_alone_reports_closed(copilot_settings):
    """AI_COPILOT_INFERENCE_ENABLED is a second opener, not an independent one.

    With the master switch off the routes 404 and no inference happens, so a true
    here would be a claim about a surface that cannot answer at all.
    """
    copilot_settings(surface=False, inference=True)

    flags = await evaluate_client_features(None, _session_factory())

    assert flags["ai_copilot"] is False
    assert flags["ai_copilot_inference"] is False


async def test_kill_switch_closes_both_halves(copilot_settings):
    """The switch that 404s the API has to silence the panel's claims with it."""
    copilot_settings(surface=True, inference=True)

    flags = await evaluate_client_features(None, _session_factory(flag_row=True))

    assert flags["ai_copilot"] is False
    assert flags["ai_copilot_inference"] is False


async def test_anonymous_caller_still_gets_a_verdict(copilot_settings):
    """No copilot permission token exists, so there is nothing to fold per-user.

    Reporting false to an unauthenticated caller would withhold the disclosure from
    the panel on its very first read, before the token refresh has landed.
    """
    copilot_settings(surface=True, inference=True)

    flags = await evaluate_client_features(None, _session_factory())

    assert flags["ai_copilot"] is True
