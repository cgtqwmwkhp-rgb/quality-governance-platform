"""Server-side execute access, conflict token, and honest push outcomes.

Start / complete / responses are reachable by the assignee or by
``audit:update``. That is a handler gate (census still records the routes as
authenticated-only until they grow a ``require_permission`` dependency).

Auto-created findings from execute must not write CEL rows. ``/compliance``
stays confirmed-only (#1811). Manual finding CEL is a separate ADR — this
module names the asymmetry so it is not smoothed away.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from src.domain.exceptions import AuthorizationError, ConflictError
from src.domain.models.audit import AuditRun
from src.domain.models.user import User
from src.domain.services.job_lifecycle_concurrency import if_match_matches, job_lifecycle_etag

EXECUTE_PERMISSION = "audit:update"

# Named so tests can pin the honesty rule without scraping comments.
AUDIT_EXECUTE_WRITES_CEL = False

PUSH_SENT = "sent"
PUSH_NO_SUB = "no_sub"
PUSH_DISABLED = "disabled"
PUSH_FAILED = "failed"
PUSH_OUTCOMES = frozenset({PUSH_SENT, PUSH_NO_SUB, PUSH_DISABLED, PUSH_FAILED})


def can_execute_run(user: User, run: AuditRun) -> bool:
    """True when the caller may start, answer, or complete this run."""
    if user.has_permission(EXECUTE_PERMISSION):
        return True
    assigned = getattr(run, "assigned_to_id", None)
    return assigned is not None and assigned == user.id


def assert_can_execute_run(user: User, run: AuditRun) -> None:
    """Refuse callers who are neither the assignee nor audit:update."""
    if can_execute_run(user, run):
        return
    raise AuthorizationError("Only the assignee or a user with audit:update may execute this audit")


def run_etag(run: AuditRun) -> Optional[str]:
    """Concurrency token: the run's ``updated_at`` in UTC ISO."""
    return job_lifecycle_etag(getattr(run, "updated_at", None))


def assert_run_if_match(run: AuditRun, if_match: Optional[str]) -> None:
    """409 when If-Match is present and does not match the row.

    Omitted If-Match stays compatible with existing clients. The execute UI
    always sends the header so two devices conflict instead of last-write-wins.
    """
    if if_match is None or not str(if_match).strip():
        return
    if if_match_matches(if_match=if_match, updated_at=getattr(run, "updated_at", None)):
        return
    current = run_etag(run)
    raise ConflictError(
        "This audit was updated on another device. Reload to continue.",
        code="STALE_WRITE",
        details={"etag": current},
    )


def classify_push_results(results: Sequence[Mapping[str, Any]] | None) -> str:
    """Map PushNotificationService rows to sent / no_sub / disabled / failed.

    Never returns ``delivered``. A skipped-disabled result wins over empty
    subscriptions so a user who opted out is not described as having no device.
    """
    rows = list(results or [])
    if not rows:
        return PUSH_NO_SUB

    def _reason(row: Mapping[str, Any]) -> str:
        return str(row.get("reason") or "").lower()

    if any("disabled" in _reason(row) for row in rows):
        return PUSH_DISABLED
    if all(str(row.get("status") or "").lower() == "skipped" and "subscription" in _reason(row) for row in rows):
        return PUSH_NO_SUB
    if any(row.get("success") is True or str(row.get("status") or "").lower() == "sent" for row in rows):
        return PUSH_SENT
    return PUSH_FAILED
