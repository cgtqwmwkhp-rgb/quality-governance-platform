"""Cancelled Staging twins must not fail-close Production.

GitHub fires workflow_run on every Staging *completed* run, including cancelled
duplicates. Pre-deployment checks already skip unless staging conclusion is
success. Notify used always() + a release gate that fails when B&D is skipped,
so those twins concluded failure even though Azure was never written.

Pin: ignore-non-success-staging names the non-event; Notify does not run when
the triggering Staging run was not success. The fail-close for a *successful*
Staging run that did not actually deploy is unchanged.
"""

from __future__ import annotations

import pathlib

import pytest

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/deploy-production.yml"


@pytest.fixture(scope="module")
def raw() -> str:
    assert WORKFLOW.exists()
    return WORKFLOW.read_text()


@pytest.fixture(scope="module")
def parsed(raw: str) -> dict:
    if yaml is None:
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(raw)


def test_pre_deployment_checks_still_require_staging_success(parsed: dict) -> None:
    condition = parsed["jobs"]["pre-deployment-checks"].get("if") or ""
    assert "workflow_run.conclusion == 'success'" in condition


def test_ignore_non_success_staging_job_runs_when_staging_was_not_success(parsed: dict) -> None:
    job = parsed["jobs"]["ignore-non-success-staging"]
    condition = job.get("if") or ""
    assert "github.event_name == 'workflow_run'" in condition
    assert "workflow_run.conclusion != 'success'" in condition
    assert job["runs-on"] == "ubuntu-latest"


def test_notify_does_not_run_on_non_success_staging(parsed: dict) -> None:
    condition = parsed["jobs"]["notify"].get("if") or ""
    assert "always()" in condition
    assert "workflow_run.conclusion != 'success'" in condition
    assert "workflow_dispatch" in condition
    assert "rollback" in condition


def test_notify_release_gate_still_fail_closes_skipped_build(raw: str) -> None:
    assert "Release gate — refuse to conclude success without a real deploy" in raw
    assert "failing this run so its conclusion does not claim a deployment" in raw
