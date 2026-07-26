"""The CORS origin regex must admit our SWA environments and nothing else.

Two failures are guarded here, and they pull in opposite directions.

Too narrow: the pattern did not match the regional hostname Azure gives a named
Static Web App environment, so the staging bake could not call the staging API.
Every console call failed CORS, the E2E gate failed on console errors, and the
production frontend deploy was skipped eleven times in a row on 26 Jul.

Too wide: the pattern it replaced matched any `*.N.azurestaticapps.net`, which
is every Static Web App on Azure. Combined with allow_credentials=True, that let
an attacker host their own SWA and make credentialed cross-origin requests.
"""

from __future__ import annotations

import re

import pytest

from src.main import create_application


def _origin_regex() -> re.Pattern[str]:
    app = create_application()
    for mw in app.user_middleware:
        pattern = mw.kwargs.get("allow_origin_regex") if hasattr(mw, "kwargs") else None
        if pattern:
            return re.compile(pattern)
    pytest.fail("no allow_origin_regex is configured on the CORS middleware")


@pytest.mark.parametrize(
    "origin",
    [
        "https://purple-water-03205fa03.6.azurestaticapps.net",
        "https://purple-water-03205fa03-staging.6.azurestaticapps.net",
        "https://purple-water-03205fa03-staging.westeurope.6.azurestaticapps.net",
        "https://purple-water-03205fa03-preview.westeurope.6.azurestaticapps.net",
    ],
)
def test_our_own_swa_environments_are_allowed(origin: str) -> None:
    assert _origin_regex().match(origin), f"{origin} must be allowed"


@pytest.mark.parametrize(
    "origin",
    [
        # Any other Static Web App. The old pattern allowed all of these.
        "https://evil-app-12345.6.azurestaticapps.net",
        "https://attacker.4.azurestaticapps.net",
        "https://purple-water-99999999.6.azurestaticapps.net",
        # Prefix and suffix smuggling around our real name.
        "https://purple-water-03205fa03.6.azurestaticapps.net.evil.com",
        "https://notpurple-water-03205fa03.6.azurestaticapps.net",
        "https://evil.com/purple-water-03205fa03.6.azurestaticapps.net",
        # Scheme downgrade.
        "http://purple-water-03205fa03.6.azurestaticapps.net",
    ],
)
def test_everything_else_is_rejected(origin: str) -> None:
    assert not _origin_regex().match(origin), f"{origin} must NOT be allowed"


def test_the_regex_is_anchored_at_both_ends() -> None:
    """An unanchored pattern is how suffix smuggling gets in."""
    pattern = _origin_regex().pattern
    assert pattern.startswith("^"), "origin regex must be anchored at the start"
    assert pattern.endswith("$"), "origin regex must be anchored at the end"
