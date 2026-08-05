"""The sweep must notify the right people, once, and nobody else.

Exercised against a real session rather than mocks, because every property worth
asserting here is a property of the database interaction: that a second run writes
nothing, that a dry run writes nothing, that a closed module reads nothing, and --
the one that matters most -- that an administrator belonging to no tenant is not
told about a tenant's obligations.

That last test exists because the precedent sweep this one replaces shipped with exactly
that defect. ``safety_asset_expiry_tasks`` admitted any admin whose ``tenant_id`` is NULL
for every row in every tenant, so such an admin received notifications naming other
customers' assets. A test that only checked "the owner got notified" would pass against
that bug, which is why this file has the test below;
``tests/integration/test_safety_asset_expiry_sweep.py`` is now its counterpart for the
sweep that had the defect.

Rows are removed explicitly in a finally: the integration conftest only calls
``drop_all`` on SQLite, so on PostgreSQL anything committed here survives into every
later test in the run.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import delete, select

from src.domain.models.compliance_schedule import ComplianceRequirement, ComplianceScheduleAnchor
from src.domain.models.notification import Notification
from src.domain.services.compliance_schedule_notifications import ENTITY_TYPE
from src.infrastructure.tasks.compliance_schedule_notification_tasks import _sweep


@pytest.fixture(autouse=True)
def _module_open(monkeypatch):
    """Open the module and clear the kill switch's 30-second verdict cache.

    Without the cache reset a verdict read by an earlier test leaks into this one,
    which would make these tests order-dependent in exactly the way that is hardest
    to diagnose later.
    """
    from src.core.config import settings
    from src.domain.services.compliance_schedule_kill_switch import reset_compliance_schedule_kill_switch_cache

    monkeypatch.setattr(settings, "compliance_schedule_enabled", True, raising=False)
    reset_compliance_schedule_kill_switch_cache()
    yield
    reset_compliance_schedule_kill_switch_cache()


async def _make_requirement(
    session,
    *,
    tenant_id: int,
    owner_id: int | None,
    days_until_due: int = 3,
    statutory: bool = True,
    deleted: bool = False,
) -> int:
    suffix = uuid.uuid4().hex[:8]
    requirement = ComplianceRequirement(
        tenant_id=tenant_id,
        reference_number=f"CSR-TEST-{suffix}",
        title="Fire risk assessment",
        taxonomy_id="FRA",
        frequency_months=12,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=statutory,
        next_due_date=date.today() + timedelta(days=days_until_due),
        owner_id=owner_id,
        is_active=True,
    )
    if deleted:
        from datetime import datetime, timezone

        requirement.deleted_at = datetime.now(timezone.utc)
    session.add(requirement)
    await session.commit()
    await session.refresh(requirement)
    return requirement.id


async def _cleanup(session, *, requirement_id: int | None) -> None:
    await session.rollback()
    await session.execute(delete(Notification).where(Notification.entity_type == ENTITY_TYPE))
    if requirement_id is not None:
        await session.execute(delete(ComplianceRequirement).where(ComplianceRequirement.id == requirement_id))
    await session.commit()


async def _compliance_notifications(session, *, requirement_id: int | None = None) -> list[Notification]:
    """Notifications for one requirement, or all compliance ones when unscoped.

    Callers should pass ``requirement_id``. A global assertion looks stronger but is
    weaker in practice: the integration conftest only calls ``drop_all`` on SQLite,
    so on PostgreSQL every row any earlier test committed is still present, and an
    unrelated requirement left behind by another test would fail these assertions
    for reasons that have nothing to do with the sweep.
    """
    stmt = select(Notification).where(Notification.entity_type == ENTITY_TYPE)
    if requirement_id is not None:
        stmt = stmt.where(Notification.entity_id == str(requirement_id))
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def test_owner_is_notified_once_and_a_second_run_writes_nothing(test_session, test_user, test_tenant):
    user_id, tenant_id = test_user.id, test_tenant.id
    requirement_id = None
    try:
        requirement_id = await _make_requirement(test_session, tenant_id=tenant_id, owner_id=user_id)

        first = await _sweep(dry_run=False)
        assert first["notifications_created"] >= 1, f"nothing was created: {first}"

        await test_session.rollback()
        delivered = await _compliance_notifications(test_session, requirement_id=requirement_id)
        mine = [n for n in delivered if n.user_id == user_id]
        assert len(mine) == 1, f"expected exactly one notification, got {len(mine)}"
        assert mine[0].entity_id == str(requirement_id)
        assert mine[0].extra_data and mine[0].extra_data.get("dedupe_key")

        second = await _sweep(dry_run=False)
        assert second["notifications_created"] == 0, f"the second run wrote something: {second}"
        assert second["notifications_skipped_existing"] >= 1

        await test_session.rollback()
        still = [
            n
            for n in await _compliance_notifications(test_session, requirement_id=requirement_id)
            if n.user_id == user_id
        ]
        assert len(still) == 1, "a duplicate reached the table"
    finally:
        await _cleanup(test_session, requirement_id=requirement_id)


async def test_dry_run_reports_what_it_would_do_and_writes_nothing(test_session, test_user, test_tenant):
    user_id, tenant_id = test_user.id, test_tenant.id
    requirement_id = None
    try:
        requirement_id = await _make_requirement(test_session, tenant_id=tenant_id, owner_id=user_id)

        result = await _sweep(dry_run=True)
        assert result["dry_run"] is True
        assert result["notifications_created"] >= 1, "a dry run must still report the count"

        await test_session.rollback()
        assert (
            await _compliance_notifications(test_session, requirement_id=requirement_id) == []
        ), "a dry run wrote to the database"
    finally:
        await _cleanup(test_session, requirement_id=requirement_id)


async def test_a_closed_module_sweeps_nothing(test_session, test_user, test_tenant, monkeypatch):
    from src.core.config import settings

    user_id, tenant_id = test_user.id, test_tenant.id
    requirement_id = None
    try:
        requirement_id = await _make_requirement(test_session, tenant_id=tenant_id, owner_id=user_id)
        monkeypatch.setattr(settings, "compliance_schedule_enabled", False, raising=False)

        result = await _sweep(dry_run=False)
        assert result["tenants_considered"] == 0, "a closed module still enumerated tenants"
        assert result["notifications_created"] == 0

        await test_session.rollback()
        assert await _compliance_notifications(test_session, requirement_id=requirement_id) == []
    finally:
        await _cleanup(test_session, requirement_id=requirement_id)


async def test_a_soft_deleted_requirement_is_not_notified(test_session, test_user, test_tenant):
    user_id, tenant_id = test_user.id, test_tenant.id
    requirement_id = None
    try:
        requirement_id = await _make_requirement(test_session, tenant_id=tenant_id, owner_id=user_id, deleted=True)

        await _sweep(dry_run=False)

        await test_session.rollback()
        assert (
            await _compliance_notifications(test_session, requirement_id=requirement_id) == []
        ), "a soft-deleted requirement produced a notification"
    finally:
        await _cleanup(test_session, requirement_id=requirement_id)


async def test_an_index_conflict_is_absorbed_and_the_run_continues(test_session, test_user, test_tenant):
    """A duplicate refused by the index must be counted, not fatal.

    Simulates the race the SAVEPOINT exists for. A concurrent worker cannot be
    scheduled deterministically, so instead a row carrying the dedupe key this run
    will generate is planted under a *different* ``entity_id``. That is invisible to
    the sweep's read-before-write fast path, which filters on ``entity_id``, but the
    partial unique index sees it, because the index is on the key and not the entity.
    The insert therefore fails exactly where a real second worker would make it fail.

    What is being asserted is not the count but the survival: if the failed insert
    poisoned the surrounding transaction, the run would abort and no later
    requirement in that tenant would be swept.
    """
    user_id, tenant_id = test_user.id, test_tenant.id
    requirement_id = None
    try:
        requirement_id = await _make_requirement(test_session, tenant_id=tenant_id, owner_id=user_id)

        from src.domain.services.compliance_schedule_notifications import dedupe_key
        from src.domain.services.compliance_schedule_policy import classify_due_band

        requirement = await test_session.get(ComplianceRequirement, requirement_id)
        band = classify_due_band(requirement.next_due_date, now=date.today())
        assert band is not None, "fixture did not land in a band, so this test proves nothing"
        planted_key = dedupe_key(requirement_id, requirement.next_due_date, band)

        from src.domain.models.notification import NotificationType

        test_session.add(
            Notification(
                user_id=user_id,
                type=NotificationType.COMPLIANCE_ALERT,
                title="Planted",
                message="Occupies the dedupe key under a different entity_id",
                entity_type=ENTITY_TYPE,
                entity_id="0",
                extra_data={"dedupe_key": planted_key},
            )
        )
        await test_session.commit()

        result = await _sweep(dry_run=False)

        assert (
            result["notifications_skipped_conflict"] >= 1
        ), f"the index conflict was not absorbed and counted: {result}"
        assert result["tenants_swept"] >= 1, f"the run aborted instead of continuing: {result}"
    finally:
        await _cleanup(test_session, requirement_id=requirement_id)


async def test_a_tenant_that_raises_is_counted_and_the_run_continues(test_session, test_user, test_tenant, monkeypatch):
    """A failed tenant must appear in the counters, not only in a log line.

    Before ``tenants_failed`` existed the only evidence was ``tenants_considered``
    exceeding the sum of the other outcomes, which required an operator to notice a
    gap by arithmetic.
    """
    import src.infrastructure.tasks.compliance_schedule_notification_tasks as task_mod

    user_id, tenant_id = test_user.id, test_tenant.id
    requirement_id = None
    try:
        requirement_id = await _make_requirement(test_session, tenant_id=tenant_id, owner_id=user_id)

        async def _boom(*_args, **_kwargs):
            raise RuntimeError("simulated failure for one tenant")

        monkeypatch.setattr(task_mod, "_sweep_tenant", _boom)

        result = await _sweep(dry_run=False)

        assert result["tenants_failed"] >= 1, f"the failed tenant was not counted: {result}"
        assert result["timed_out"] is False, "an ordinary failure was misreported as a timeout"
        outcomes = (
            result["tenants_swept"]
            + result["tenants_failed"]
            + result["tenants_skipped_locked"]
            + result["tenants_skipped_closed"]
        )
        assert (
            outcomes == result["tenants_considered"]
        ), f"tenant outcomes {outcomes} do not account for {result['tenants_considered']} considered: {result}"
    finally:
        await _cleanup(test_session, requirement_id=requirement_id)


async def test_a_soft_time_limit_returns_partial_counters_instead_of_dying(
    test_session, test_user, test_tenant, monkeypatch
):
    """The soft limit must truncate the run, not be swallowed as a per-tenant failure.

    ``SoftTimeLimitExceeded`` subclasses ``Exception``, so the per-tenant handler would
    absorb it and carry on to the next tenant -- defeating the soft limit entirely and
    letting the run continue until the hard limit kills the worker mid-transaction,
    losing every counter. This asserts it propagates to the loop, is recorded, and the
    result survives.
    """
    from celery.exceptions import SoftTimeLimitExceeded

    import src.infrastructure.tasks.compliance_schedule_notification_tasks as task_mod

    user_id, tenant_id = test_user.id, test_tenant.id
    requirement_id = None
    try:
        requirement_id = await _make_requirement(test_session, tenant_id=tenant_id, owner_id=user_id)

        async def _timeout(*_args, **_kwargs):
            raise SoftTimeLimitExceeded()

        monkeypatch.setattr(task_mod, "_sweep_tenant", _timeout)

        result = await _sweep(dry_run=False)

        assert result["timed_out"] is True, f"the timeout was not recorded: {result}"
        assert result["tenants_failed"] == 0, "a timeout was miscounted as a tenant failure"
        assert result["tenants_considered"] >= 1, "the result dict did not survive the timeout"
    finally:
        await _cleanup(test_session, requirement_id=requirement_id)


async def test_an_admin_belonging_to_no_tenant_is_never_a_recipient(test_session, test_user, test_tenant):
    """The cross-tenant leak guard. This is the test the precedent sweep used to fail.

    A NULL-tenant admin exists in real deployments, and the obvious implementation
    -- ``tenant_id IS NULL OR tenant_id = :tenant`` -- hands them every tenant's
    obligations by name.
    """
    from src.core.security import get_password_hash
    from src.domain.models.user import Role, User, user_roles

    tenant_id = test_tenant.id
    requirement_id = None
    stray_admin_id = None
    created_role_id = None
    try:
        role_rows = await test_session.execute(select(Role).where(Role.name == "admin"))
        admin_role = role_rows.scalars().first()
        if admin_role is None:
            # Created rather than skipped. Skipping would retire the only test that
            # catches a cross-tenant leak on whichever harness happens to lack the
            # row, which is the SQLite one the suite uses by default.
            admin_role = Role(name="admin", description="Test admin role", is_system_role=False)
            test_session.add(admin_role)
            await test_session.commit()
            await test_session.refresh(admin_role)
            created_role_id = admin_role.id

        stray = User(
            email=f"stray-admin-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("testpassword123"),
            first_name="Stray",
            last_name="Admin",
            is_active=True,
            is_superuser=False,
            tenant_id=None,
        )
        stray.roles.append(admin_role)
        test_session.add(stray)
        await test_session.commit()
        await test_session.refresh(stray)
        stray_admin_id = stray.id

        # No owner, so admins are the fallback for every band. If a NULL-tenant
        # admin were eligible, this is the run that would reach them.
        requirement_id = await _make_requirement(test_session, tenant_id=tenant_id, owner_id=None)

        await _sweep(dry_run=False)

        await test_session.rollback()
        delivered = await _compliance_notifications(test_session, requirement_id=requirement_id)
        leaked = [n for n in delivered if n.user_id == stray_admin_id]
        assert leaked == [], (
            f"an admin belonging to no tenant received {len(leaked)} notification(s) about "
            f"tenant {tenant_id}'s obligations"
        )
    finally:
        await _cleanup(test_session, requirement_id=requirement_id)
        if stray_admin_id is not None:
            # The association row is removed with a Core delete rather than
            # ``user.roles.clear()``: touching that collection on an expired
            # instance triggers a lazy load, which raises MissingGreenlet on an
            # async session and turns cleanup into a test failure.
            await test_session.execute(delete(user_roles).where(user_roles.c.user_id == stray_admin_id))
            await test_session.execute(delete(User).where(User.id == stray_admin_id))
            await test_session.commit()
        if created_role_id is not None:
            await test_session.execute(delete(Role).where(Role.id == created_role_id))
            await test_session.commit()
