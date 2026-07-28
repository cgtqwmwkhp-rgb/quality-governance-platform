"""Dump the portal-intake payloads the Locust tasks build, as JSON, for contract tests.

Usage: ``python -m tests.performance.capture_portal_payloads <output.json>``

This exists as a script rather than a helper the test imports because importing
Locust runs ``gevent.monkey.patch_all()`` on the process, which deadlocks an
asyncio test runner. The test that checks these payloads against the real intake
handler therefore captures them in a subprocess.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any, Callable

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.performance.locustfile import PortalUser, QGPUser  # noqa: E402

PORTAL_REPORTS_PATH = "/api/v1/portal/reports/"

# Enough repeats to reach every random branch of the tasks (report_type ×
# is_anonymous). The consumer de-duplicates, so this only has to be generous.
TASK_REPEATS = 60
TASK_SEED = 20260728

CAPTURED_TASKS: dict[str, tuple[type, str]] = {
    "QGPUser.submit_quick_report": (QGPUser, "submit_quick_report"),
    "PortalUser.submit_incident": (PortalUser, "submit_incident"),
}


class _StubResponse:
    """Minimal stand-in for a Locust response, for tasks using catch_response."""

    status_code = 201
    text = '{"success": true}'

    def __enter__(self) -> "_StubResponse":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def success(self) -> None:
        pass

    def failure(self, message: str) -> None:
        pass


class _PayloadRecorder:
    """Captures what a Locust task would have sent, without sending it."""

    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []

    def post(self, path: str, json: Any = None, name: str | None = None, **_: Any) -> _StubResponse:
        self.posts.append({"path": path, "json": json})
        return _StubResponse()

    def get(self, path: str, **_: Any) -> _StubResponse:
        return _StubResponse()


class _StubUser:
    """Stands in for a Locust user instance, without an Environment or runner.

    Class-level task constants (expected-status sets and the like) are read off the
    real user class, so a task keeps seeing the values it would see in a real run.
    """

    def __init__(self, owner: type) -> None:
        self._owner = owner
        self.client = _PayloadRecorder()
        self.token = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._owner, name)

    @property
    def auth_headers(self) -> dict[str, str]:
        return {}


def capture_report_payloads(owner: type, task_name: str) -> list[dict[str, Any]]:
    """Return every payload ``owner.task_name`` posts to the portal report endpoint."""
    task: Callable = getattr(owner, task_name)
    user = _StubUser(owner)
    state = random.getstate()
    try:
        random.seed(TASK_SEED)
        for _ in range(TASK_REPEATS):
            task(user)
    finally:
        random.setstate(state)
    return [post["json"] for post in user.client.posts if post["path"] == PORTAL_REPORTS_PATH]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0] if argv else 'capture_portal_payloads'} <output.json>", file=sys.stderr)
        return 2
    captured = {name: capture_report_payloads(owner, task_name) for name, (owner, task_name) in CAPTURED_TASKS.items()}
    Path(argv[1]).write_text(json.dumps(captured, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
