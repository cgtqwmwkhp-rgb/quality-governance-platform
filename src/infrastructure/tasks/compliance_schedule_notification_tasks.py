"""Daily sweep that notifies owners and admins about due compliance obligations.

Scheduled daily at **08:15 UTC** via ``celery_app.conf.beat_schedule``
(``sweep-compliance-schedule-due``). The beat entry is the deploy-time on/off
lever; the faster lever (no deploy) is the kill switch, which this task asks at
entry and again at each tenant boundary. Manual ``dry_run`` remains the right
first run in any environment that has never swept.

What this task is careful about, and why
----------------------------------------
Four things here are not incidental, and the closest precedent in this repository
(``safety_asset_expiry_tasks``) shipped to production getting three of them wrong.
They are called out so the next person to copy a sweep copies this one.

**Tenant isolation is explicit, not inherited.** Admin recipients are selected with
``User.tenant_id == tenant_id`` and nothing else. The precedent additionally admitted
any admin whose ``tenant_id`` is NULL, for *every* row in *every* tenant, so such an
admin received notifications naming other customers' assets; it now resolves
recipients the way this module does. There is no band of this sweep where telling one
tenant's administrator about another tenant's fire risk assessment is correct, so a
NULL-tenant user is simply not a recipient. If cross-tenant oversight is ever wanted
it needs its own deliberate design, not a NULL check.

**The GUC is bound per tenant.** Today the worker connects as a role with
``BYPASSRLS`` -- measured, not assumed -- so an unbound sweep sees every tenant and
appears to work. After the RLS cutover the same code sees *zero* rows and this task
would silently notify nobody while reporting success. Binding
``app.current_tenant_id`` per tenant means the query is correct under both
configurations, and the per-tenant loop is what makes binding possible at all.

**One sweep at a time, per tenant.** ``task_acks_late`` is on, so a worker lost
mid-run has its task redelivered and a second copy can overlap the first. A
transaction-scoped advisory lock per tenant means the second copy skips that tenant
rather than racing it. The lock is not correctness for duplicates -- the partial
unique index on ``notifications`` is -- but it stops two workers doing the same work
and reporting it twice.

**Soft-deleted rows are excluded.** ``is_active`` and ``deleted_at`` are different
questions and both matter: a deleted requirement is not merely inactive, and
notifying about it would resurrect it in the recipient's inbox.

Why a SAVEPOINT per insert rather than ``ON CONFLICT DO NOTHING``
----------------------------------------------------------------
``ON CONFLICT`` was the original design, and PostgreSQL can infer the partial
expression index correctly -- verified directly. It is not used because
``INSERT ... ON CONFLICT`` is dialect-specific, and expressing the inference for an
expression index requires the PostgreSQL dialect's own construct. That would leave
this loop untestable on the SQLite harness the unit and integration suites use by
default, and an untestable concurrency path is a worse trade than a nested
transaction. A SAVEPOINT achieves the same thing -- a failed insert does not poison
the surrounding transaction -- on both dialects, and the ``IntegrityError`` it
catches is the index doing its job, which is worth counting rather than hiding.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any, Optional, Sequence, TypedDict

from celery.exceptions import SoftTimeLimitExceeded

from src.infrastructure.tasks.celery_app import celery_app

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: Namespace for the per-tenant advisory lock. Any fixed 32-bit value works; this
#: one is arbitrary but must never be reused by another sweep, or two unrelated
#: tasks would exclude each other for the same tenant.
SWEEP_LOCK_NAMESPACE = 0x51475043

ADMIN_ROLE_ENV = "COMPLIANCE_SCHEDULE_ADMIN_ROLE"
DEFAULT_ADMIN_ROLE = "admin"


class ComplianceSweepResults(TypedDict):
    """Counters a run reports. Every skip has its own field, on purpose.

    A single ``skipped`` total cannot distinguish "already notified yesterday",
    which is the healthy steady state, from "the database refused a duplicate",
    which means two workers overlapped, from "the module was closed", which means
    an operator intervened. Collapsing them would hide exactly the signals worth
    watching after the first run.
    """

    tenants_considered: int
    tenants_swept: int
    tenants_failed: int
    tenants_skipped_locked: int
    tenants_skipped_closed: int
    requirements_scanned: int
    in_band: int
    notifications_created: int
    notifications_skipped_existing: int
    notifications_skipped_conflict: int
    emails_enqueued: int
    emails_skipped: int
    recipients_unresolved: int
    dry_run: bool
    timed_out: bool
    evaluated_at: str
    admin_role: str


def _admin_role_name() -> str:
    return (os.getenv(ADMIN_ROLE_ENV) or DEFAULT_ADMIN_ROLE).strip() or DEFAULT_ADMIN_ROLE


def _empty_results(*, dry_run: bool, evaluated_at: datetime) -> ComplianceSweepResults:
    return {
        "tenants_considered": 0,
        "tenants_swept": 0,
        "tenants_failed": 0,
        "tenants_skipped_locked": 0,
        "tenants_skipped_closed": 0,
        "requirements_scanned": 0,
        "in_band": 0,
        "notifications_created": 0,
        "notifications_skipped_existing": 0,
        "notifications_skipped_conflict": 0,
        "emails_enqueued": 0,
        "emails_skipped": 0,
        "recipients_unresolved": 0,
        "dry_run": dry_run,
        "timed_out": False,
        "evaluated_at": evaluated_at.isoformat(),
        "admin_role": _admin_role_name(),
    }


async def _is_postgres(session: "AsyncSession") -> bool:
    bind = session.get_bind()
    return getattr(getattr(bind, "dialect", None), "name", None) == "postgresql"


async def _try_tenant_lock(session: "AsyncSession", tenant_id: int) -> bool:
    """Take a transaction-scoped advisory lock for this tenant, or report failure.

    Returns True on non-PostgreSQL: SQLite has no advisory locks and the test
    harness runs one sweep at a time, so refusing to proceed there would make the
    task untestable rather than safer.
    """
    from sqlalchemy import text

    if not await _is_postgres(session):
        return True

    acquired = await session.execute(
        text("SELECT pg_try_advisory_xact_lock(:namespace, :tenant_id)"),
        {"namespace": SWEEP_LOCK_NAMESPACE, "tenant_id": tenant_id},
    )
    return bool(acquired.scalar())


async def _active_tenant_ids(session: "AsyncSession") -> Sequence[int]:
    from sqlalchemy import select

    from src.domain.models.tenant import Tenant

    rows = await session.execute(select(Tenant.id).where(Tenant.is_active.is_(True)).order_by(Tenant.id))
    return list(rows.scalars().all())


async def _admin_user_ids(session: "AsyncSession", tenant_id: int) -> list[int]:
    """Active, non-deleted admins **of this tenant**.

    No NULL-tenant fallback. See the module docstring: that fallback was the
    cross-tenant leak in the precedent sweep, which now mirrors this query.
    """
    from sqlalchemy import select

    from src.domain.models.user import Role, User

    rows = await session.execute(
        select(User.id)
        .join(User.roles)
        .where(
            Role.name == _admin_role_name(),
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .order_by(User.id)
    )
    return list(rows.scalars().all())


async def _due_requirements(session: "AsyncSession", tenant_id: int) -> Sequence[Any]:
    from sqlalchemy import select

    from src.domain.models.compliance_schedule import ComplianceRequirement

    rows = await session.execute(
        select(ComplianceRequirement)
        .where(
            ComplianceRequirement.tenant_id == tenant_id,
            ComplianceRequirement.is_active.is_(True),
            ComplianceRequirement.deleted_at.is_(None),
        )
        .order_by(ComplianceRequirement.id)
    )
    return list(rows.scalars().all())


async def _existing_notifications(
    session: "AsyncSession",
    *,
    requirement_id: int,
    user_ids: Sequence[int],
) -> Sequence[Any]:
    from sqlalchemy import select

    from src.domain.models.notification import Notification
    from src.domain.services.compliance_schedule_notifications import ENTITY_TYPE

    if not user_ids:
        return []

    rows = await session.execute(
        select(Notification).where(
            Notification.entity_type == ENTITY_TYPE,
            Notification.entity_id == str(requirement_id),
            Notification.user_id.in_(list(user_ids)),
        )
    )
    return list(rows.scalars().all())


async def _user_email_pref_enabled(session: "AsyncSession", user_id: int) -> bool:
    from sqlalchemy import select

    from src.domain.models.notification import NotificationPreference

    result = await session.execute(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    prefs = result.scalar_one_or_none()
    if prefs is None:
        return True
    return bool(prefs.email_enabled)


async def _maybe_enqueue_due_reminder_email(
    session: "AsyncSession",
    *,
    tenant_id: int,
    user_id: int,
    kwargs: dict[str, Any],
    results: ComplianceSweepResults,
) -> None:
    """Best-effort email after a successful COMPLIANCE_ALERT insert. Never raises."""
    from src.domain.services.compliance_schedule_notify_flags import email_channel_enabled

    try:
        if not await email_channel_enabled(session, tenant_id=tenant_id):
            results["emails_skipped"] += 1
            return
        if not await _user_email_pref_enabled(session, user_id):
            results["emails_skipped"] += 1
            return

        from sqlalchemy import select

        from src.domain.models.user import User
        from src.infrastructure.tasks.email_tasks import send_email

        row = await session.execute(select(User.email).where(User.id == user_id))
        recipient = row.scalar_one_or_none()
        if not recipient:
            results["emails_skipped"] += 1
            return

        body = f"{kwargs['message']}\n\nOpen: {kwargs['action_url']}"
        send_email.delay(recipient, kwargs["title"], body, False)
        results["emails_enqueued"] += 1
    except Exception:
        results["emails_skipped"] += 1
        logger.warning(
            "Compliance schedule due-reminder email enqueue failed for user %s",
            user_id,
            exc_info=True,
        )


async def _sweep_tenant(
    session: "AsyncSession",
    *,
    tenant_id: int,
    today: date,
    evaluated_at: datetime,
    dry_run: bool,
    results: ComplianceSweepResults,
) -> None:
    from sqlalchemy.exc import IntegrityError

    from src.domain.models.notification import Notification
    from src.domain.services.compliance_schedule_notifications import (
        build_notification_kwargs,
        notification_exists_for_key,
        recipient_user_ids,
    )
    from src.domain.services.compliance_schedule_notify_flags import due_reminder_notify_enabled
    from src.domain.services.compliance_schedule_policy import classify_due_band

    if not await due_reminder_notify_enabled(session, tenant_id=tenant_id):
        logger.info(
            "Compliance schedule sweep: due reminder notify flag off for tenant %d; skipping",
            tenant_id,
        )
        return

    requirements = await _due_requirements(session, tenant_id)
    results["requirements_scanned"] += len(requirements)
    if not requirements:
        return

    admin_ids = await _admin_user_ids(session, tenant_id)

    for requirement in requirements:
        band = classify_due_band(requirement.next_due_date, now=today)
        if band is None:
            continue
        results["in_band"] += 1

        recipients = recipient_user_ids(
            owner_user_id=requirement.owner_id,
            admin_user_ids=admin_ids,
            band=band,
            statutory=bool(requirement.statutory),
        )
        if not recipients:
            # Neither an owner nor an admin of this tenant. Counted rather than
            # skipped silently: an obligation nobody can be told about is a
            # configuration problem someone has to see.
            results["recipients_unresolved"] += 1
            continue

        existing = await _existing_notifications(
            session,
            requirement_id=requirement.id,
            user_ids=recipients,
        )

        for user_id in recipients:
            if notification_exists_for_key(
                existing,
                user_id=user_id,
                requirement_id=requirement.id,
                due_date=requirement.next_due_date,
                band=band,
            ):
                results["notifications_skipped_existing"] += 1
                continue

            if dry_run:
                results["notifications_created"] += 1
                continue

            kwargs = build_notification_kwargs(
                user_id=user_id,
                tenant_id=tenant_id,
                requirement_id=requirement.id,
                reference_number=requirement.reference_number,
                title=requirement.title,
                band=band,
                due_date=requirement.next_due_date,
                statutory=bool(requirement.statutory),
                evaluated_at=evaluated_at,
            )
            try:
                async with session.begin_nested():
                    session.add(Notification(**kwargs))
            except IntegrityError:
                # The partial unique index refused it, so another worker inserted
                # the same reminder between the read above and this write. That is
                # the index doing precisely what it was added for.
                results["notifications_skipped_conflict"] += 1
            else:
                results["notifications_created"] += 1
                await _maybe_enqueue_due_reminder_email(
                    session,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    kwargs=kwargs,
                    results=results,
                )


async def _sweep(*, dry_run: bool, today: Optional[date] = None) -> ComplianceSweepResults:
    from src.domain.services.compliance_schedule_kill_switch import compliance_schedule_is_open
    from src.infrastructure.database import async_session_maker

    evaluated_at = datetime.now(timezone.utc)
    effective_today = today or evaluated_at.date()
    results = _empty_results(dry_run=dry_run, evaluated_at=evaluated_at)

    # Asked before any session is opened. A module switched off in configuration
    # must cost nothing, and this is the cheapest possible place to find out.
    if not await compliance_schedule_is_open(async_session_maker):
        logger.info("Compliance schedule sweep: module closed, nothing swept")
        return results

    async with async_session_maker() as session:
        tenant_ids = await _active_tenant_ids(session)
        results["tenants_considered"] = len(tenant_ids)

    try:
        await _sweep_all_tenants(
            tenant_ids,
            today=effective_today,
            evaluated_at=evaluated_at,
            dry_run=dry_run,
            results=results,
        )
    except SoftTimeLimitExceeded:
        # Returned rather than re-raised, so the counters describing what *was*
        # delivered survive. The sweep is idempotent -- the dedupe index refuses a
        # repeat and the read-before-write skips it -- so a truncated run needs no
        # compensation: the next run, scheduled or manual, finishes the remainder.
        # Retrying here instead would discard these counters and start again.
        results["timed_out"] = True
        logger.warning(
            "Compliance schedule sweep hit its soft time limit after %d of %d tenant(s); "
            "returning partial results, the remainder is picked up by the next run",
            results["tenants_swept"],
            results["tenants_considered"],
        )

    logger.info("Compliance schedule sweep completed: %s", results)
    return results


async def _sweep_all_tenants(
    tenant_ids: Sequence[int],
    *,
    today: date,
    evaluated_at: datetime,
    dry_run: bool,
    results: ComplianceSweepResults,
) -> None:
    """The per-tenant loop. Separated so its caller can catch a soft timeout.

    Mutates ``results`` rather than returning one, because a run cut short partway
    must still report what it managed. A return value would be lost on the exception
    that cuts it short, which is the whole failure this separation exists to avoid.
    """
    from src.domain.services.compliance_schedule_kill_switch import compliance_schedule_is_open
    from src.infrastructure.database import async_session_maker
    from src.infrastructure.middleware.tenant_context import apply_tenant_guc

    for position, tenant_id in enumerate(tenant_ids):
        # Re-asked per tenant so an operator engaging the kill switch part-way
        # through stops the run at the next tenant boundary rather than after it.
        # Cheap: the switch caches its verdict for 30 seconds.
        if not await compliance_schedule_is_open(async_session_maker):
            # Counted from the loop position, not from tenants_swept: a tenant that
            # was locked or that raised was still reached, and calling it
            # "skipped because closed" would misattribute why it was not swept.
            results["tenants_skipped_closed"] += len(tenant_ids) - position
            logger.warning(
                "Compliance schedule sweep: kill switch engaged mid-run, stopping with %d tenant(s) unswept",
                len(tenant_ids) - position,
            )
            return

        # One session and therefore one transaction per tenant: the advisory lock
        # is transaction-scoped, and a tenant that fails must not roll back the
        # notifications already written for another.
        async with async_session_maker() as session:
            try:
                if not await _try_tenant_lock(session, tenant_id):
                    results["tenants_skipped_locked"] += 1
                    logger.info(
                        "Compliance schedule sweep: tenant %d already being swept, skipping",
                        tenant_id,
                    )
                    continue

                await apply_tenant_guc(session, tenant_id)
                await _sweep_tenant(
                    session,
                    tenant_id=tenant_id,
                    today=today,
                    evaluated_at=evaluated_at,
                    dry_run=dry_run,
                    results=results,
                )

                if dry_run:
                    await session.rollback()
                else:
                    await session.commit()
                results["tenants_swept"] += 1
            except SoftTimeLimitExceeded:
                # Must not be swallowed by the handler below. The soft limit exists so
                # a task can stop while it still has time to stop cleanly; treating it
                # as "this tenant failed, try the next one" defeats it entirely and the
                # run continues until the hard limit kills the worker mid-transaction,
                # taking the result dict with it. Re-raised to the loop, which records
                # the truncation and returns what was actually done.
                await session.rollback()
                raise
            except Exception:
                await session.rollback()
                results["tenants_failed"] += 1
                logger.exception(
                    "Compliance schedule sweep failed for tenant %d; continuing with the rest",
                    tenant_id,
                )


@celery_app.task(
    name="src.infrastructure.tasks.compliance_schedule_notification_tasks.sweep_compliance_schedule_due",
    queue="notifications",
    bind=True,
    max_retries=3,
    # Overrides the global 300s soft / 600s hard limits, which are sized for
    # request-shaped work. This sweep walks every tenant and its whole register, so
    # 300s is a limit it can reach legitimately rather than only through a fault --
    # and the global limit arriving mid-run is indistinguishable from a real failure.
    #
    # Still finite, and finite is the point: on the soft limit the sweep returns its
    # partial counters and the next run finishes the rest, which is safe because every
    # write is idempotent. The hard limit remains the backstop for a genuinely wedged
    # run, sitting far enough above the soft one to leave room to unwind cleanly.
    soft_time_limit=900,
    time_limit=1200,
)
def sweep_compliance_schedule_due(
    self,
    dry_run: bool = False,
    today: Optional[str] = None,
) -> ComplianceSweepResults:
    """Notify owners and admins about obligations entering a reminder band.

    ``dry_run`` computes everything and writes nothing, rolling back each tenant's
    transaction. Use it for the first run in any environment: a register seeded
    with historical due dates has a backlog, and the count it reports is how many
    notifications a real run would deliver at once.

    ``today`` is an ISO date overriding the band reference point. It exists for
    tests and for replaying a missed day; it does not change what is due, only
    which band a requirement falls into.
    """
    reference = date.fromisoformat(today) if today else None
    try:
        return asyncio.run(_sweep(dry_run=dry_run, today=reference))
    except Exception as exc:
        logger.error("Compliance schedule sweep failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=300)
