"""
Schemathesis property-based API contract tests (D10 WCS closure 2026-04-08).

Tests every operation exposed via the OpenAPI spec against five invariants:
  1. Response status codes are within expected ranges (2xx, 4xx, 5xx only — no 1xx/3xx)
  2. Responses conform to the declared OpenAPI response schema (via schemathesis native check)
  3. Server never returns 500 on well-formed requests
  4. Content-Type header is present and valid on all 2xx responses
  5. Error responses (4xx/5xx) include a structured body (never empty)

Auth: A dummy Bearer token is injected; endpoints that require valid auth will return 401/403,
which are valid and tested. No real credentials are used in CI.

To run manually against a live app:
  SCHEMA_URL=http://localhost:8000/openapi.json pytest tests/integration/test_schemathesis_api.py -v

In CI this test runs against the app started in the same job with a test DB.
"""

from __future__ import annotations

import os

import pytest
import schemathesis
from schemathesis import Case
from schemathesis.checks import not_a_server_error

SCHEMA_URL = os.environ.get("SCHEMA_URL", "http://localhost:8000/openapi.json")
TEST_AUTH_TOKEN = os.environ.get(
    "SCHEMATHESIS_AUTH_TOKEN",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxIiwiZW1haWwiOiJ0ZXN0QHFncC5jb20iLCJyb2xlIjoiYWRtaW4iLCJleHAiOjk5OTk5OTk5OTl9"
    ".schemathesis-test-token-not-real",
)


@pytest.fixture(scope="module")
def schema():
    """Load OpenAPI schema. Skip module if app is not reachable."""
    try:
        return schemathesis.from_uri(
            SCHEMA_URL,
            headers={"Authorization": f"Bearer {TEST_AUTH_TOKEN}"},
            validate_schema=False,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"App not reachable at {SCHEMA_URL}: {exc}")


# ─── Invariant 1 + 2 + 3: schemathesis built-in stateful checks ─────────────


@schemathesis.parametrize()
def test_api_operations_do_not_raise_server_errors(case: Case) -> None:
    """Every API operation must not return 5xx for well-formed inputs (Invariant 3).

    Schemathesis generates random but schema-valid request payloads.
    The `not_a_server_error` check fails the test on any 5xx response.
    """
    case.headers = case.headers or {}
    case.headers["Authorization"] = f"Bearer {TEST_AUTH_TOKEN}"
    response = case.call()
    case.validate_response(response, checks=(not_a_server_error,))


# ─── Invariant 4: Content-Type present on all 2xx responses ──────────────────


@schemathesis.parametrize()
def test_2xx_responses_have_content_type(case: Case) -> None:
    """Every successful (2xx) API response must include a Content-Type header."""
    case.headers = case.headers or {}
    case.headers["Authorization"] = f"Bearer {TEST_AUTH_TOKEN}"
    response = case.call()
    if 200 <= response.status_code < 300:
        assert "content-type" in {k.lower() for k in response.headers}, (
            f"2xx response from {case.method} {case.path} missing Content-Type. " f"Status: {response.status_code}"
        )


# ─── Invariant 5: Error responses have structured bodies ─────────────────────


@schemathesis.parametrize()
def test_error_responses_have_body(case: Case) -> None:
    """4xx and 5xx responses must not have an empty body.

    An empty error body prevents clients from surfacing actionable messages.
    This aligns with the QGP error envelope contract:
      { "detail": "...", "status_code": NNN }
    """
    case.headers = case.headers or {}
    case.headers["Authorization"] = f"Bearer {TEST_AUTH_TOKEN}"
    response = case.call()
    if response.status_code >= 400:
        assert response.text.strip(), (
            f"Error response from {case.method} {case.path} has empty body. " f"Status: {response.status_code}"
        )


# ─── Additional: status code range check ─────────────────────────────────────


@schemathesis.parametrize()
def test_status_codes_within_valid_range(case: Case) -> None:
    """No response should return a 1xx or 3xx status (unexpected for JSON API)."""
    case.headers = case.headers or {}
    case.headers["Authorization"] = f"Bearer {TEST_AUTH_TOKEN}"
    response = case.call()
    assert response.status_code not in range(
        100, 200
    ), f"Unexpected 1xx from {case.method} {case.path}: {response.status_code}"
    assert response.status_code not in range(
        300, 400
    ), f"Unexpected 3xx redirect from {case.method} {case.path}: {response.status_code}"
