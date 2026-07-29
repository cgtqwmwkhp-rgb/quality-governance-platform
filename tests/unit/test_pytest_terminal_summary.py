"""C-57: pytest terminal summary must not call a failing run production-ready."""

from tests.conftest import format_suite_verdict


def test_suite_failed_when_any_failure_even_if_pass_rate_above_95():
    """One failure in twenty is 95% — the old hook printed PRODUCTION READY."""
    message, colour = format_suite_verdict(passed=19, failed=1, skipped=0, errors=0)
    assert colour == "red"
    assert "SUITE FAILED" in message
    assert "PRODUCTION READY" not in message


def test_suite_failed_when_errors_present_even_with_high_pass_rate():
    message, colour = format_suite_verdict(passed=99, failed=0, skipped=0, errors=1)
    assert colour == "red"
    assert "SUITE FAILED" in message
    assert "PRODUCTION READY" not in message


def test_skipped_inflate_rate_but_do_not_claim_production_ready():
    """95 passed + 5 skipped is a 95% rate of 'total' but is not a clean green."""
    message, colour = format_suite_verdict(passed=95, failed=0, skipped=5, errors=0)
    assert colour == "yellow"
    assert "SKIPPED" in message
    assert "PRODUCTION READY" not in message


def test_empty_collection_is_not_green():
    message, colour = format_suite_verdict(passed=0, failed=0, skipped=0, errors=0)
    assert colour == "red"
    assert "NO TESTS RAN" in message


def test_clean_run_is_green_without_production_ready_claim():
    message, colour = format_suite_verdict(passed=20, failed=0, skipped=0, errors=0)
    assert colour == "green"
    assert "passed" in message
    assert "PRODUCTION READY" not in message
