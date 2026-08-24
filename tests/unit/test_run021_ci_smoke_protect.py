"""PX-197 must not inventory dedicated CI / smoke-runner accounts."""

from __future__ import annotations

from scripts.ops.run021._common import CI_SMOKE_USER_EMAILS, is_protected_ci_smoke_email, matches_test_token


def test_ci_smoke_emails_are_protected() -> None:
    for email in CI_SMOKE_USER_EMAILS:
        assert is_protected_ci_smoke_email(email)
        assert is_protected_ci_smoke_email(email.upper())


def test_ordinary_smoke_debris_still_matches() -> None:
    assert matches_test_token("smoke-test-20260201204913@example.com")
    assert not is_protected_ci_smoke_email("smoke-test-20260201204913@example.com")


def test_protected_helper_rejects_blank() -> None:
    assert not is_protected_ci_smoke_email(None)
    assert not is_protected_ci_smoke_email("")
    assert not is_protected_ci_smoke_email("david.harris@plantexpand.com")
