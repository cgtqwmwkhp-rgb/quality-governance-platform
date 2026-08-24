"""The sweep must be importable by the worker and scheduled exactly once.

Every failure mode below is silent, which is why each is pinned by a test.

Registration: ``celery_app`` lists task modules explicitly because
``autodiscover_tasks`` looks for a nested ``tasks.tasks`` module and silently skips
these siblings -- the worker starts, answers a ping, and raises ``NotRegistered`` the
moment anything is sent to it. A module that is never added to that tuple fails
exactly that way, in production, with no import error to point at.

Scheduling: ``beat_schedule`` names its task as a dotted string, so a typo or a later
rename yields an entry that dispatches to nothing, once a day, into a log. Two entries
for the same task are equally quiet, because the dedupe key means the second sweep
sends nothing a user would see.

Start time: two cross-tenant sweeps beginning on the same minute contend for one
worker pool, and 07:00 to 08:00 is already crowded.
"""

from __future__ import annotations

import pytest

from src.infrastructure.tasks.celery_app import CELERY_TASK_MODULES, celery_app

MODULE_PATH = "src.infrastructure.tasks.compliance_schedule_notification_tasks"
TASK_NAME = f"{MODULE_PATH}.sweep_compliance_schedule_due"


def test_the_worker_is_told_to_import_this_module():
    assert MODULE_PATH in CELERY_TASK_MODULES, (
        f"{MODULE_PATH} is missing from CELERY_TASK_MODULES, so the worker will raise "
        "NotRegistered when the sweep is sent to it"
    )


def test_the_task_is_registered_under_its_full_dotted_name():
    import src.infrastructure.tasks.compliance_schedule_notification_tasks  # noqa: F401

    assert TASK_NAME in celery_app.tasks, f"{TASK_NAME} is not in the task registry"


def test_the_sweep_is_scheduled_exactly_once():
    """One beat entry, and only one.

    This assertion replaced `test_this_module_contributes_no_beat_entry`, which held
    while the task was registered but unscheduled and was the guard that kept
    scheduling in its own change. That change is this one, so the guard is inverted
    rather than deleted: it now pins the lever's existence instead of its absence.

    "Exactly once" is the part worth keeping. Two entries for the same task means two
    sweeps a day, and because each notification is deduplicated per occurrence and
    band the second would be silent -- no duplicate reaches a user, so nothing would
    reveal the mistake except the run counters nobody is watching yet.
    """
    scheduled = [
        name for name, entry in celery_app.conf.beat_schedule.items() if MODULE_PATH in str(entry.get("task", ""))
    ]
    assert len(scheduled) == 1, f"expected exactly one beat entry for the sweep, found {scheduled}"


def test_the_beat_entry_points_at_the_task_that_exists():
    """Guards the failure mode a string-keyed schedule invites.

    ``beat_schedule`` names its task as a dotted string, so a typo or a later rename
    produces a beat entry that dispatches to nothing. Beat itself does not complain;
    the worker raises NotRegistered once a day, in a log, where it can sit unnoticed
    for a long time.
    """
    entry = next(
        entry for name, entry in celery_app.conf.beat_schedule.items() if MODULE_PATH in str(entry.get("task", ""))
    )
    assert entry["task"] == TASK_NAME, f"beat dispatches to {entry['task']!r}, which is not the registered task name"
    assert TASK_NAME in celery_app.tasks, "beat names a task that is not in the registry"


def test_the_sweep_does_not_share_a_start_minute_with_another_sweep():
    """Two cross-tenant sweeps starting on the same minute contend for one worker pool.

    The 07:00-08:00 stretch is already occupied by competency expiry, safety asset
    expiry, library review reminders and the horizon scan. This pins the separation so
    a later edit cannot quietly stack this sweep on top of one of them.
    """
    entry = next(
        entry for name, entry in celery_app.conf.beat_schedule.items() if MODULE_PATH in str(entry.get("task", ""))
    )
    ours = entry["schedule"]

    clashing = [
        name
        for name, other in celery_app.conf.beat_schedule.items()
        if MODULE_PATH not in str(other.get("task", ""))
        and getattr(other.get("schedule"), "hour", None) == ours.hour
        and getattr(other.get("schedule"), "minute", None) == ours.minute
    ]
    assert clashing == [], f"the sweep starts at the same time as {clashing}"


def test_the_admin_role_is_configurable_and_falls_back(monkeypatch):
    from src.infrastructure.tasks.compliance_schedule_notification_tasks import (
        ADMIN_ROLE_ENV,
        DEFAULT_ADMIN_ROLE,
        _admin_role_name,
    )

    monkeypatch.delenv(ADMIN_ROLE_ENV, raising=False)
    assert _admin_role_name() == DEFAULT_ADMIN_ROLE

    monkeypatch.setenv(ADMIN_ROLE_ENV, "tenant_administrator")
    assert _admin_role_name() == "tenant_administrator"

    # Whitespace-only must not silently become the recipient query's role name,
    # which would match nothing and make the sweep notify owners only.
    monkeypatch.setenv(ADMIN_ROLE_ENV, "   ")
    assert _admin_role_name() == DEFAULT_ADMIN_ROLE


def test_every_counter_a_runbook_will_quote_is_present():
    from src.infrastructure.tasks.compliance_schedule_notification_tasks import ComplianceSweepResults

    expected = {
        "tenants_considered",
        "tenants_swept",
        "tenants_failed",
        "tenants_skipped_locked",
        "tenants_skipped_closed",
        "requirements_scanned",
        "in_band",
        "notifications_created",
        "notifications_skipped_existing",
        "notifications_skipped_conflict",
        "emails_enqueued",
        "emails_skipped",
        "recipients_unresolved",
        "dry_run",
        "timed_out",
        "evaluated_at",
        "admin_role",
    }
    assert set(ComplianceSweepResults.__annotations__) == expected


def test_the_tenant_outcomes_account_for_every_tenant():
    """Every way a tenant can end must have its own counter.

    Without ``tenants_failed`` the only way to notice a tenant that raised was to
    subtract the other three from ``tenants_considered`` and find a gap. An operator
    reading a result dict at 3am should not have to do arithmetic to discover that a
    customer was skipped.
    """
    from src.infrastructure.tasks.compliance_schedule_notification_tasks import ComplianceSweepResults

    outcomes = {"tenants_swept", "tenants_failed", "tenants_skipped_locked", "tenants_skipped_closed"}
    assert outcomes <= set(
        ComplianceSweepResults.__annotations__
    ), f"missing tenant outcome counters: {outcomes - set(ComplianceSweepResults.__annotations__)}"


def test_the_sweep_is_given_time_limits_of_its_own():
    """A cross-tenant sweep must not inherit request-shaped limits.

    The global configuration is 300s soft and 600s hard, which is right for the work a
    web request queues and wrong for a job that walks every tenant's register. Left on
    the default, the soft limit is reachable on a legitimate run, and a limit that
    fires in normal operation is indistinguishable from a fault.
    """
    task = celery_app.tasks[TASK_NAME]
    assert task.soft_time_limit is not None, "the sweep inherits the global soft limit"
    assert task.time_limit is not None, "the sweep inherits the global hard limit"
    assert task.soft_time_limit > celery_app.conf.task_soft_time_limit
    assert task.time_limit > task.soft_time_limit, (
        "the hard limit must sit above the soft one, or the sweep is killed before it "
        "can return its partial counters"
    )


@pytest.mark.parametrize("field", ["notifications_skipped_existing", "notifications_skipped_conflict"])
def test_the_two_skip_reasons_stay_separate(field):
    """A single ``skipped`` total would hide the signal worth watching.

    "Already notified yesterday" is the healthy steady state. "The database refused a
    duplicate" means two workers overlapped. Collapsing them makes the second
    invisible.
    """
    from src.infrastructure.tasks.compliance_schedule_notification_tasks import ComplianceSweepResults

    assert field in ComplianceSweepResults.__annotations__
