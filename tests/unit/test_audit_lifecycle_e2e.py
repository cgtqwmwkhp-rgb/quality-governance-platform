from unittest.mock import MagicMock, patch

import requests

from scripts.smoke.audit_lifecycle_e2e import _request, run


def test_request_retries_timeout_then_succeeds() -> None:
    success_response = MagicMock()
    success_response.status_code = 200

    with patch(
        "scripts.smoke.audit_lifecycle_e2e.requests.request",
        side_effect=[
            requests.exceptions.ReadTimeout("timed out"),
            requests.exceptions.ReadTimeout("timed out"),
            success_response,
        ],
    ) as request_mock:
        with patch("scripts.smoke.audit_lifecycle_e2e.time.sleep") as sleep_mock:
            response = _request("POST", "https://example.test/api/v1/auth/login", payload={"email": "a"})

    assert response is success_response
    assert request_mock.call_count == 3
    assert sleep_mock.call_count == 2


def test_run_returns_failed_login_step_when_request_errors() -> None:
    with patch(
        "scripts.smoke.audit_lifecycle_e2e._request",
        side_effect=RuntimeError("Request to https://example.test/api/v1/auth/login failed after 3 attempts"),
    ):
        results = run("https://example.test", "user@example.com", "secret")

    assert len(results) == 1
    assert results[0].name == "login"
    assert results[0].passed is False
    assert "failed after 3 attempts" in results[0].detail
