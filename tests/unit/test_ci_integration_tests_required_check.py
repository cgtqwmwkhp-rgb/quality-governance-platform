"""Pin the Integration Tests required-check name onto a non-matrix aggregator.

Branch protection requires a status check named exactly ``Integration Tests``.
GitHub Actions appends `` (N)`` to matrix job *display* names, so putting that
exact name on a matrix job publishes ``Integration Tests (1)``, ``(2)``, … and
detaches the required context — blocking every PR until someone with admin
rights repairs branch protection.

Shards therefore use a different name; a thin aggregator keeps the exact
required name and fails closed when any shard fails or is cancelled.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_YML = REPO_ROOT / ".github/workflows/ci.yml"

REQUIRED_CHECK_NAME = "Integration Tests"
SHARD_JOB_ID = "integration-test-shards"
AGGREGATOR_JOB_ID = "integration-tests"


def _load_jobs() -> dict[str, Any]:
    document = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))
    assert isinstance(document, dict), "ci.yml did not parse to a mapping"
    jobs = document.get("jobs")
    assert isinstance(jobs, dict) and jobs, "ci.yml has no jobs"
    return jobs


def _needs_list(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs")
    if needs is None:
        return []
    if isinstance(needs, str):
        return [needs]
    assert isinstance(needs, list), f"unexpected needs type: {type(needs)}"
    return [str(item) for item in needs]


def assert_integration_tests_required_check_shape(jobs: dict[str, Any]) -> None:
    """Fail loudly when the required-check shape drifts."""
    assert SHARD_JOB_ID in jobs, f"missing shard job id {SHARD_JOB_ID!r}"
    assert AGGREGATOR_JOB_ID in jobs, f"missing aggregator job id {AGGREGATOR_JOB_ID!r}"

    shard = jobs[SHARD_JOB_ID]
    aggregator = jobs[AGGREGATOR_JOB_ID]
    assert isinstance(shard, dict) and isinstance(aggregator, dict)

    shard_name = shard.get("name")
    aggregator_name = aggregator.get("name")

    assert aggregator_name == REQUIRED_CHECK_NAME, (
        f"aggregator job {AGGREGATOR_JOB_ID!r} must be named exactly "
        f"{REQUIRED_CHECK_NAME!r} (branch protection); got {aggregator_name!r}"
    )
    assert shard_name != REQUIRED_CHECK_NAME, (
        f"matrix shard job must NOT be named {REQUIRED_CHECK_NAME!r} — GitHub "
        f"would publish '{REQUIRED_CHECK_NAME} (1)' etc. and detach the required "
        f"check; got shard name {shard_name!r}"
    )
    assert (
        shard_name == "Integration Test Shard"
    ), f"expected shard display name 'Integration Test Shard', got {shard_name!r}"

    strategy = shard.get("strategy") or {}
    assert isinstance(strategy, dict) and "matrix" in strategy, f"{SHARD_JOB_ID} must define strategy.matrix"
    matrix = strategy["matrix"]
    assert isinstance(matrix, dict) and "shard" in matrix, f"{SHARD_JOB_ID} matrix must include a 'shard' key"

    agg_strategy = aggregator.get("strategy") or {}
    assert "matrix" not in agg_strategy, (
        f"aggregator {AGGREGATOR_JOB_ID} must not be a matrix job " f"(would rename the required check)"
    )

    assert SHARD_JOB_ID in _needs_list(aggregator), (
        f"aggregator {AGGREGATOR_JOB_ID} must needs: [{SHARD_JOB_ID}] so it " f"fails closed with the shards"
    )

    # Downstream gates must keep depending on the aggregator job id (whose
    # display name is the required check), not on the matrix shard job alone.
    for dependent_id in ("all-checks", "quality-trend"):
        assert dependent_id in jobs, f"missing {dependent_id} job"
        dependent_needs = _needs_list(jobs[dependent_id])
        assert AGGREGATOR_JOB_ID in dependent_needs, (
            f"{dependent_id} must still need {AGGREGATOR_JOB_ID} "
            f"(required-check aggregator); needs={dependent_needs}"
        )
        assert SHARD_JOB_ID not in dependent_needs, (
            f"{dependent_id} must not need {SHARD_JOB_ID} directly — that would "
            f"bypass the named aggregator; needs={dependent_needs}"
        )


def test_integration_tests_required_check_uses_non_matrix_aggregator() -> None:
    assert_integration_tests_required_check_shape(_load_jobs())


def test_renaming_aggregator_away_from_required_name_fails_the_pin() -> None:
    """Negative control: the pin must notice if the aggregator name drifts."""
    jobs = copy.deepcopy(_load_jobs())
    jobs[AGGREGATOR_JOB_ID]["name"] = "Integration Tests Aggregator"

    with pytest.raises(AssertionError, match="must be named exactly"):
        assert_integration_tests_required_check_shape(jobs)


def test_naming_the_matrix_job_integration_tests_fails_the_pin() -> None:
    """Negative control: the dangerous matrix rename must not slip through."""
    jobs = copy.deepcopy(_load_jobs())
    jobs[SHARD_JOB_ID]["name"] = REQUIRED_CHECK_NAME

    with pytest.raises(AssertionError, match="must NOT be named"):
        assert_integration_tests_required_check_shape(jobs)


def test_shards_do_not_enforce_suite_coverage_floor() -> None:
    """A quarter of the suite cannot meet the estate floor; the aggregator owns EG-05."""
    text = CI_YML.read_text(encoding="utf-8")
    assert (
        "--cov-fail-under=0" in text
    ), "shard pytest must disable cov-fail-under so a green shard is not failed for coverage"


def test_integration_tests_aggregator_has_no_continue_on_error() -> None:
    """CI Security Covenant forbids continue-on-error inside critical job integration-tests."""
    import re

    text = CI_YML.read_text(encoding="utf-8")
    m = re.search(r"(?ms)^  integration-tests:\n(.*?)(?=^  \w[\w-]*:|\Z)", text)
    assert m, "integration-tests job missing"
    assert not re.search(
        r"^        continue-on-error:\s*true\s*$", m.group(1), re.M
    ), "continue-on-error inside integration-tests trips the Stage 2.0 covenant"
