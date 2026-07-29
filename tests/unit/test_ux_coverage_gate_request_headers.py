"""Playwright must not inject request headers the API's CORS policy refuses.

`tests/ux-coverage/playwright.config.ts` set ``extraHTTPHeaders: {'X-Test-Context':
'ux-coverage-audit'}``. Playwright applies ``extraHTTPHeaders`` to every request the
browser makes, including cross-origin XHR from the audited frontend to the API. A
custom header makes those requests non-simple, so the browser sends a CORS preflight
naming ``x-test-context`` in ``Access-Control-Request-Headers``. That name is not in
the API's ``allow_headers``, so the preflight was answered 400, the browser blocked
the request, and the service worker converted the failure into a synthetic
``503 {"error": "Offline", "message": "Network unavailable"}``.

The gate therefore broke every API call made by the application it was auditing and
reported the damage as an application defect: the P0 ``portal-incident-report``
journey dead-ended on "Unable to Load Form" waiting for ``field-contract``, and the
fake 503 was read three times over as staging being unavailable.

These tests drive the real CORS middleware, so they fail if a header is added to a
Playwright config without also being allowed by the API — in either direction.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]

PLAYWRIGHT_CONFIGS = (
    REPO_ROOT / "tests" / "ux-coverage" / "playwright.config.ts",
    REPO_ROOT / "frontend" / "playwright.config.ts",
)

# The origin the UX coverage gate actually drives (scripts/governance/resolve-ux-frontend-url.cjs
# derives this named staging environment of the Static Web App).
AUDITED_ORIGIN = "https://purple-water-03205fa03-staging.6.azurestaticapps.net"


def _strip_line_comments(source: str) -> str:
    """Drop `//` comments so commented-out config is not read as config.

    Deliberately line-based: the configs use `//` only, and a full TS parse is not
    warranted. Block comments are stripped separately.
    """
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return "\n".join(re.sub(r"//.*$", "", line) for line in source.splitlines())


def extract_extra_http_headers(source: str) -> list[str]:
    """Return the header names an `extraHTTPHeaders` block injects.

    Returns an empty list when no such block is configured.
    """
    code = _strip_line_comments(source)
    match = re.search(r"extraHTTPHeaders\s*:\s*\{", code)
    if match is None:
        return []

    # Walk to the matching close brace so nested objects cannot truncate the block.
    depth = 0
    start = match.end() - 1
    end = None
    for index in range(start, len(code)):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
    if end is None:
        raise AssertionError("extraHTTPHeaders block is not closed")

    block = code[start + 1 : end]
    return re.findall(r"""['"]?([A-Za-z0-9-]+)['"]?\s*:""", block)


class TestExtraHeaderParser:
    """The parser must not report "no headers" for a config that sets them."""

    def test_finds_a_configured_header(self):
        source = """
        export default defineConfig({
          use: {
            viewport: { width: 1280, height: 720 },
            extraHTTPHeaders: {
              'X-Test-Context': 'ux-coverage-audit',
              'X-Request-Id': 'abc',
            },
          },
        });
        """
        assert extract_extra_http_headers(source) == ["X-Test-Context", "X-Request-Id"]

    def test_ignores_commented_out_headers(self):
        source = """
        use: {
          // extraHTTPHeaders: { 'X-Test-Context': 'ux-coverage-audit' },
        },
        """
        assert extract_extra_http_headers(source) == []

    def test_absent_block_yields_no_headers(self):
        assert extract_extra_http_headers("use: { viewport: { width: 1280 } }") == []


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestPlaywrightHeadersSurvivePreflight:
    """Every header a Playwright config injects must pass a real CORS preflight."""

    @pytest.mark.parametrize("config_path", PLAYWRIGHT_CONFIGS, ids=lambda p: p.parent.name)
    def test_injected_headers_are_allowed_by_cors(self, client, config_path):
        assert config_path.is_file(), f"missing Playwright config: {config_path}"
        headers = extract_extra_http_headers(config_path.read_text(encoding="utf-8"))

        for header in headers:
            requested = f"authorization,{header.lower()}"
            response = client.options(
                "/api/v1/admin/config/lookup/customers",
                headers={
                    "Origin": AUDITED_ORIGIN,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": requested,
                },
            )
            assert response.status_code == 200, (
                f"{config_path.relative_to(REPO_ROOT)} injects '{header}' into every browser "
                f"request, but the API answers the CORS preflight for it with "
                f"{response.status_code}. The browser will block every cross-origin API call "
                f"the audited app makes. Either drop the header or add it to allow_headers "
                f"in src/main.py."
            )
            allowed = response.headers.get("access-control-allow-headers", "").lower()
            assert header.lower() in allowed, (
                f"{config_path.relative_to(REPO_ROOT)} injects '{header}' but it is absent "
                f"from access-control-allow-headers ({allowed!r})."
            )

    def test_preflight_baseline_succeeds(self, client):
        """Guards the test above from passing because preflight always 200s.

        `authorization` alone must be accepted, and an unlisted header must not be —
        otherwise the assertions above prove nothing.
        """
        allowed = client.options(
            "/api/v1/admin/config/lookup/customers",
            headers={
                "Origin": AUDITED_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert allowed.status_code == 200

        refused = client.options(
            "/api/v1/admin/config/lookup/customers",
            headers={
                "Origin": AUDITED_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,x-test-context",
            },
        )
        assert refused.status_code != 200, (
            "An unlisted request header now passes preflight, so this suite can no "
            "longer detect a Playwright config injecting a refused header."
        )
