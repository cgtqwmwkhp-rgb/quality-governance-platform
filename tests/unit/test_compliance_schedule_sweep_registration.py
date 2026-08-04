"""The sweep must be importable by the worker and absent from the beat schedule.

Both halves are real failure modes here, not hypotheticals.

Registration: ``celery_app`` lists task modules explicitly because
``autodiscover_tasks`` looks for a nested ``tasks.tasks`` module and silently skips
these siblings -- the worker starts, answers a ping, and raises ``NotRegistered`` the
moment anything is sent to it. A module that is never added to that tuple fails
exactly that way, in production, with no import error to point at.

Absence from beat: scheduling is deliberately a separate change so that switching
this sweep off is a one-line revert. If a beat entry ever arrives in this module,
that lever is gone and nobody would notice until they needed it.
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


def test_this_module_contributes_no_beat_entry():
    scheduled = [
        name for name, entry in celery_app.conf.beat_schedule.items() if MODULE_PATH in str(entry.get("task", ""))
    ]
    assert scheduled == [], (
        f"beat entries {scheduled} schedule this sweep. Scheduling belongs in its own "
        "change so that disabling it stays a one-line revert."
    )


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
        "tenants_skipped_locked",
        "tenants_skipped_closed",
        "requirements_scanned",
        "in_band",
        "notifications_created",
        "notifications_skipped_existing",
        "notifications_skipped_conflict",
        "recipients_unresolved",
        "dry_run",
        "evaluated_at",
        "admin_role",
    }
    assert set(ComplianceSweepResults.__annotations__) == expected


@pytest.mark.parametrize("field", ["notifications_skipped_existing", "notifications_skipped_conflict"])
def test_the_two_skip_reasons_stay_separate(field):
    """A single ``skipped`` total would hide the signal worth watching.

    "Already notified yesterday" is the healthy steady state. "The database refused a
    duplicate" means two workers overlapped. Collapsing them makes the second
    invisible.
    """
    from src.infrastructure.tasks.compliance_schedule_notification_tasks import ComplianceSweepResults

    assert field in ComplianceSweepResults.__annotations__
