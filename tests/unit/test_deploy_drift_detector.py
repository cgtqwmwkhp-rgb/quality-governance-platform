"""The drift detector must report a stalled deploy, and must not cry wolf during a live one.

Why this workflow exists at all: `deploy-production.yml` already verifies runtime identity
properly, polling `/api/v1/meta/version` until `build_sha` matches the release SHA. But that
check runs *inside* a deploy. On 2026-08-05 two production deploys failed at the release
gate before reaching it, so nothing executed and nothing reported that production had been
serving an hour-old commit — it was found by hand.

A detector that fires on every merge is worse than none, because people learn to ignore it.
So the grace window is as load-bearing as the comparison, and both are pinned here.
"""

from __future__ import annotations

import pathlib

import pytest

try:  # pragma: no cover - exercised by whichever branch runs
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/deploy-drift-detector.yml"


@pytest.fixture(scope="module")
def raw() -> str:
    assert WORKFLOW.exists(), f"{WORKFLOW} is missing"
    return WORKFLOW.read_text()


@pytest.fixture(scope="module")
def parsed(raw: str) -> dict:
    if yaml is None:
        pytest.skip("PyYAML is not installed; the shell-level assertions still run")
    return yaml.safe_load(raw)


def test_it_runs_on_a_clock_not_only_on_a_deploy(parsed: dict) -> None:
    """The whole point: a deploy that never starts cannot report on itself.

    ``on`` is parsed by YAML as the boolean True, which is a long-standing trap in
    GitHub workflow files.
    """
    triggers = parsed.get("on", parsed.get(True))
    assert (
        "schedule" in triggers
    ), "without a schedule this can only report when someone asks, which is the gap it exists to close"
    assert triggers["schedule"], "schedule is declared but empty"


def test_the_schedule_is_frequent_enough_to_catch_a_stall(parsed: dict) -> None:
    triggers = parsed.get("on", parsed.get(True))
    crons = [entry["cron"] for entry in triggers["schedule"]]
    assert any(cron.startswith("*/30") or cron.startswith("*/15") for cron in crons), (
        f"cron {crons} is coarser than the ~20 minute deploy it watches, so a stall could "
        "persist well beyond the point a person would want to know"
    )


def test_both_environments_are_checked(raw: str) -> None:
    assert 'check_env "Staging"' in raw
    assert 'check_env "Production"' in raw, "production is the environment that matters most"


def test_a_recent_commit_is_not_reported_as_drift(raw: str) -> None:
    """The anti-noise guarantee.

    Immediately after a merge, every environment is legitimately behind main. A detector
    that reports that is indistinguishable from one that is broken.
    """
    assert "AGE_MINUTES" in raw and "GRACE_MINUTES" in raw, "no grace window, so this fires on every merge"
    assert (
        '"$AGE_MINUTES" -lt "$GRACE_MINUTES"' in raw
    ), "the grace window is declared but not compared, so it cannot suppress anything"


def test_the_grace_path_does_not_set_the_failure_flag(raw: str) -> None:
    """Suppressing the message but still failing would be the worst of both."""
    grace_block = raw.split('if [ "$AGE_MINUTES" -lt "$GRACE_MINUTES" ]; then', 1)[1]
    grace_block = grace_block.split("fi", 1)[0]
    assert "DRIFTED=1" not in grace_block, "an in-flight deploy is being counted as drift"


def test_an_unreachable_environment_is_not_called_drift(raw: str) -> None:
    """A down app and a stale app are different problems and must read differently."""
    assert "unreachable" in raw, "an unreachable environment is not distinguished from a stale one"
    assert "reports no build_sha" in raw, (
        "a 200 with no build_sha means identity cannot be checked; treating that as "
        "'current' would make the detector claim proof it does not have"
    )


def test_it_fails_the_run_rather_than_only_logging(raw: str) -> None:
    """Today's lesson twice over: a green tick hid a real problem both times."""
    assert "::error title=" in raw, "nothing surfaces outside the log"
    assert raw.rstrip().endswith(
        'echo "No drift: every environment is serving main."'
    ), "the success path should be the last thing in the script, after the failure exit"
    assert "exit 1" in raw


def test_missing_secrets_are_a_misconfiguration_not_a_silent_pass(raw: str) -> None:
    """An unset app name would otherwise curl an empty host and read as drift, or worse, pass."""
    assert "Drift detector misconfigured" in raw
    assert 'if [ -z "${STAGING_APP:-}" ] || [ -z "${PROD_APP:-}" ]; then' in raw


def test_it_does_not_stop_at_the_first_drifted_environment(raw: str) -> None:
    """Staging being behind must not hide production being behind."""
    check_body = raw.split("check_env() {", 1)[1].split("\n          }", 1)[0]
    assert (
        "exit 1" not in check_body
    ), "check_env exits on the first problem, so a drifted staging would mask production"
