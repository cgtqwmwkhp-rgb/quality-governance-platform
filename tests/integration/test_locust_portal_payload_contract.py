"""The Locust portal-intake payloads must be ones the live API accepts.

The `Locust Load Test` gate has one signal: the aggregate error rate. A load task
that posts a payload the API is right to reject spends that budget on itself, so a
real regression then has to be large enough to clear the quota the load test is
already using. These tests take the payloads the Locust tasks actually build and
put them through the real intake handler, so a load task cannot bake in a 4xx.

The payloads are captured in a subprocess because importing Locust runs
``gevent.monkey.patch_all()``, which deadlocks the asyncio test runner. See
``tests/performance/capture_portal_payloads.py``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

PORTAL_REPORTS_PATH = "/api/v1/portal/reports/"
_REPO_ROOT = Path(__file__).resolve().parents[2]

# (report_type, is_anonymous) combinations each task is expected to generate.
# PX-312: anonymous variants are gone — API hard-rejects is_anonymous=true.
_EXPECTED_VARIANTS: dict[str, set[tuple[str, bool]]] = {
    "QGPUser.submit_quick_report": {
        ("incident", False),
        ("complaint", False),
    },
    "PortalUser.submit_incident": {("incident", False)},
}


@pytest.fixture(scope="module")
def captured_locust_payloads(tmp_path_factory) -> dict[str, list[dict[str, Any]]]:
    """Payloads the Locust portal tasks build, captured out of process."""
    out_path = tmp_path_factory.mktemp("locust-payloads") / "payloads.json"
    result = subprocess.run(
        [sys.executable, "-m", "tests.performance.capture_portal_payloads", str(out_path)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"payload capture failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    captured = json.loads(out_path.read_text(encoding="utf-8"))
    assert set(captured) == set(_EXPECTED_VARIANTS), captured
    return captured


def _variants(payloads: list[dict[str, Any]]) -> dict[tuple[str, bool], dict[str, Any]]:
    """One representative payload per ``(report_type, is_anonymous)`` branch.

    De-duplicating keeps the number of requests this test makes independent of the
    tasks' RNG.
    """
    variants: dict[tuple[str, bool], dict[str, Any]] = {}
    for payload in payloads:
        assert isinstance(payload, dict), f"non-object payload: {payload!r}"
        variants.setdefault((str(payload.get("report_type")), bool(payload.get("is_anonymous"))), payload)
    return variants


@pytest.mark.parametrize("task_name", sorted(_EXPECTED_VARIANTS))
async def test_locust_portal_payloads_are_accepted(client, captured_locust_payloads, task_name):
    payloads = captured_locust_payloads[task_name]
    assert payloads, f"{task_name} sent no POST to {PORTAL_REPORTS_PATH}"

    variants = _variants(payloads)
    # Pin the branches so this cannot pass by exercising nothing: the named
    # (is_anonymous=False) branches are the ones that used to be rejected.
    assert set(variants) == _EXPECTED_VARIANTS[task_name], variants

    for key, payload in sorted(variants.items()):
        response = await client.post(PORTAL_REPORTS_PATH, json=payload)
        assert (
            response.status_code == 201
        ), f"{task_name} {key} payload {payload!r} rejected: {response.status_code} {response.text}"
        assert response.json()["reference_number"]
