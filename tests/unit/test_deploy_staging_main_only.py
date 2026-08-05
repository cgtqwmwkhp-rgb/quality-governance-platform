"""Staging must not deploy from a non-main workflow_run head_branch.

The workflow_run trigger already filters branches: [main], but that is the only
thing between a CI completion on some other ref and the staging→production chain.
The job-level head_branch == 'main' guard is belt-and-braces; this test pins it.
"""

from __future__ import annotations

import pathlib

import pytest

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/deploy-staging.yml"


@pytest.fixture(scope="module")
def raw() -> str:
    assert WORKFLOW.exists()
    return WORKFLOW.read_text()


@pytest.fixture(scope="module")
def parsed(raw: str) -> dict:
    if yaml is None:
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(raw)


def test_build_and_deploy_requires_main_head_branch(parsed: dict, raw: str) -> None:
    job = parsed["jobs"]["build-and-deploy"]
    condition = job.get("if") or ""
    assert "workflow_run.head_branch == 'main'" in condition, (
        "without an explicit head_branch == 'main' guard, a successful CI run on a "
        "non-main ref could start the staging→production deploy chain"
    )
    assert "workflow_run.conclusion == 'success'" in condition


def test_workflow_dispatch_still_works(parsed: dict) -> None:
    condition = parsed["jobs"]["build-and-deploy"].get("if") or ""
    assert "workflow_dispatch" in condition


def test_staging_concurrency_does_not_cancel_in_progress(parsed: dict) -> None:
    """In-flight staging must finish; cancel-in-progress thrash blocks prod promotion."""
    concurrency = parsed.get("concurrency") or {}
    assert concurrency.get("group") == "deploy-staging"
    assert concurrency.get("cancel-in-progress") is False, (
        "cancel-in-progress: true cancels mid-deploy staging runs; App Service can be "
        "LIVE on a SHA whose staging run never concludes success, so production "
        "fail-closes and never promotes via the governed path"
    )

