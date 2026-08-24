"""The API and the Celery worker must be told the same thing about feature flags.

A flag the worker *evaluates* but is never *given* does not fail loudly. The process
starts, the schedule fires, the task runs, and the sweep decides the module is disabled
because an unset environment variable reads as ``False``. Nothing errors and nothing is
delivered, so the only symptom is silence -- which is indistinguishable from "there was
nothing due". That happened to the staging Compliance Schedule sweep, and it was found by
measuring the sweep's own counters rather than by any alert.

The fix is that both blocks read one expression. This test is what stops them drifting
apart again, since the drift is invisible at runtime by construction.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = (
    Path(".github/workflows/deploy-production.yml"),
    Path(".github/workflows/deploy-staging.yml"),
)

# Flags read by code that runs on the Celery worker or beat, so they must be set on those
# apps as well as on the API. Adding to this set should be a deliberate act: the entry is
# the claim that some scheduled task consults the flag.
#
# COMPLIANCE_SCHEDULE_ENABLED: compliance_schedule_notification_tasks' sweep resolves it
# through compliance_schedule_is_open -> settings.compliance_schedule_enabled.
WORKER_EVALUATED_FLAGS = ("COMPLIANCE_SCHEDULE_ENABLED",)

# The loop that configures "<app>-worker" and "<app>-beat".
_CELERY_LOOP = re.compile(r"for celery_app in .*?\n\s*done", re.DOTALL)


def _split_api_and_celery(text: str) -> tuple[str, str]:
    """Return the workflow text before the Celery loop, and the loop itself."""
    match = _CELERY_LOOP.search(text)
    assert match is not None, "could not find the Celery app-settings loop"
    return text[: match.start()], match.group(0)


def _assignments(block: str, flag: str) -> list[str]:
    return re.findall(rf'{re.escape(flag)}="([^"]*)"', block)


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
@pytest.mark.parametrize("flag", WORKER_EVALUATED_FLAGS)
def test_worker_is_given_every_flag_it_evaluates(workflow: Path, flag: str) -> None:
    api_block, celery_block = _split_api_and_celery(workflow.read_text())

    api = _assignments(api_block, flag)
    celery = _assignments(celery_block, flag)

    assert api, f"{workflow.name}: {flag} is not set on the API app at all"
    assert celery, (
        f"{workflow.name}: {flag} is set on the API but not on the Celery apps. "
        "The worker evaluates it and treats unset as disabled, so the scheduled task "
        "will silently no-op while the module appears enabled."
    )


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
@pytest.mark.parametrize("flag", WORKER_EVALUATED_FLAGS)
def test_both_blocks_read_one_expression(workflow: Path, flag: str) -> None:
    """Being set in both places is not enough -- they must resolve to the same value.

    Hardcoding the worker's copy, or sourcing it from a different variable, restores the
    original defect while looking like the fix.
    """
    api_block, celery_block = _split_api_and_celery(workflow.read_text())
    expressions = set(_assignments(api_block, flag)) | set(_assignments(celery_block, flag))

    assert len(expressions) == 1, (
        f"{workflow.name}: {flag} is assigned from more than one expression "
        f"({sorted(expressions)}), so the API and worker can disagree."
    )


# ---------------------------------------------------------------------------
# Post-deploy live parity (catches manual `az` drift after a successful write)
# ---------------------------------------------------------------------------
#
# Deploy-time write parity (above) is necessary but not sufficient: anyone can
# later change one App Service with `az webapp config appsettings set` and the
# next deploy is the only thing that would heal it. The post-deploy step reads
# the live values and fails hard if they disagree.

_POSTDEPLOY_PARITY_STEP = re.compile(
    r"- name:\s*Assert COMPLIANCE_SCHEDULE_ENABLED API/worker live parity\n"
    r"\s+run:\s*\|\n"
    r"(?P<body>.*?)(?=\n      - name:|\n  [a-zA-Z]|\Z)",
    re.DOTALL,
)

_APPSETTINGS_LIST = re.compile(
    r"az webapp config appsettings list\s+.*?-n\s+\"([^\"]+)\"\s+.*?"
    r"--query\s+\"\[\?name=='\$FLAG'\]\.value\s*\|\s*\[0\]\"",
    re.DOTALL,
)


def _postdeploy_parity_body(text: str) -> str:
    match = _POSTDEPLOY_PARITY_STEP.search(text)
    assert match is not None, "missing step 'Assert COMPLIANCE_SCHEDULE_ENABLED API/worker live parity'"
    return match.group("body")


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
@pytest.mark.parametrize("flag", WORKER_EVALUATED_FLAGS)
def test_postdeploy_reads_flag_from_api_and_worker(workflow: Path, flag: str) -> None:
    """Both apps must be queried for the same setting key after deploy.

    Writing the flag at deploy time is not enough: a later manual `az` edit can
    reintroduce divergence. This step is the after-the-fact assertion.
    """
    body = _postdeploy_parity_body(workflow.read_text())

    assert f"FLAG={flag}" in body, f"{workflow.name}: post-deploy parity step does not pin FLAG={flag}"

    targets = _APPSETTINGS_LIST.findall(body)
    assert any(
        "API_APP" in t for t in targets
    ), f"{workflow.name}: post-deploy parity does not read appsettings from the API app"
    assert any(
        "WORKER_APP" in t for t in targets
    ), f"{workflow.name}: post-deploy parity does not read appsettings from the worker app"
    assert (
        'WORKER_APP="${API_APP}-worker"' in body or 'WORKER_APP="${API_APP}-worker"' in body
    ), f"{workflow.name}: worker app name must follow the existing '<api>-worker' convention"


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
def test_postdeploy_fails_when_api_and_worker_disagree(workflow: Path) -> None:
    """A mismatch must be a hard error, not a warning swallowed by `|| true`."""
    body = _postdeploy_parity_body(workflow.read_text())

    assert (
        'if [ "${API_VAL}" != "${WORKER_VAL}" ]' in body
    ), f"{workflow.name}: post-deploy parity step does not compare API_VAL to WORKER_VAL"
    assert "exit 1" in body, f"{workflow.name}: post-deploy parity step must exit 1 when values differ"
    # The Celery *write* path still warns with || echo; this *read* path must not.
    assert "|| true" not in body, f"{workflow.name}: post-deploy parity must not swallow failures with '|| true'"


def test_postdeploy_parity_present_in_both_workflows() -> None:
    """Removing the check from one environment is exactly how silent drift returns."""
    missing = [p.name for p in WORKFLOWS if _POSTDEPLOY_PARITY_STEP.search(p.read_text()) is None]
    assert not missing, f"post-deploy COMPLIANCE_SCHEDULE_ENABLED parity step missing from: {missing}"
