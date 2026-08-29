"""AUD-DEV-2: execute authz, If-Match conflict, honest push outcomes, CEL pin."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.domain.exceptions import AuthorizationError, ConflictError
from src.domain.services.audit_execute_access import (
    AUDIT_EXECUTE_WRITES_CEL,
    PUSH_DISABLED,
    PUSH_FAILED,
    PUSH_NO_SUB,
    PUSH_OUTCOMES,
    PUSH_SENT,
    assert_can_execute_run,
    assert_run_if_match,
    can_execute_run,
    classify_push_results,
    run_etag,
)


class _User:
    def __init__(self, uid: int, perms: frozenset[str] = frozenset()) -> None:
        self.id = uid
        self._perms = perms

    def has_permission(self, permission: str) -> bool:
        return permission in self._perms


def test_execute_writes_cel_stays_false():
    assert AUDIT_EXECUTE_WRITES_CEL is False


def test_assignee_can_execute_without_update_permission():
    run = SimpleNamespace(assigned_to_id=7)
    assert can_execute_run(_User(7), run) is True
    assert can_execute_run(_User(8), run) is False


def test_audit_update_can_execute_unassigned_run():
    run = SimpleNamespace(assigned_to_id=None)
    updater = _User(1, frozenset({"audit:update"}))
    assert can_execute_run(updater, run) is True
    assert can_execute_run(_User(1), run) is False


def test_assert_can_execute_run_refuses_stranger():
    run = SimpleNamespace(assigned_to_id=3)
    with pytest.raises(AuthorizationError):
        assert_can_execute_run(_User(9), run)


def test_omitted_if_match_is_compatible():
    run = SimpleNamespace(updated_at=datetime(2026, 8, 29, 10, tzinfo=timezone.utc))
    assert_run_if_match(run, None)
    assert_run_if_match(run, "  ")


def test_mismatched_if_match_is_stale_write_not_last_write_wins():
    stamp = datetime(2026, 8, 29, 10, tzinfo=timezone.utc)
    run = SimpleNamespace(updated_at=stamp)
    with pytest.raises(ConflictError) as exc:
        assert_run_if_match(run, "2026-01-01T00:00:00+00:00")
    assert exc.value.code == "STALE_WRITE"
    assert exc.value.details.get("etag") == run_etag(run)


def test_matching_if_match_allows_write():
    stamp = datetime(2026, 8, 29, 10, tzinfo=timezone.utc)
    run = SimpleNamespace(updated_at=stamp)
    assert_run_if_match(run, run_etag(run))


def test_classify_push_never_returns_delivered():
    assert "delivered" not in PUSH_OUTCOMES
    assert classify_push_results(None) == PUSH_NO_SUB
    assert classify_push_results([]) == PUSH_NO_SUB
    assert classify_push_results([{"status": "skipped", "reason": "No active subscriptions"}]) == PUSH_NO_SUB
    assert classify_push_results([{"status": "skipped", "reason": "Push notifications disabled"}]) == PUSH_DISABLED
    assert classify_push_results([{"success": True, "status": "sent"}]) == PUSH_SENT
    assert classify_push_results([{"success": False, "status": "failed"}]) == PUSH_FAILED
    assert classify_push_results([{"status": "skipped", "reason": "Push notifications disabled"}]) != "delivered"
