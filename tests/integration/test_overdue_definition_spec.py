"""The canonical definition of "overdue", written down so the next surface can reuse it.

PX-149 was three surfaces reporting 4, 0 and 10 for the same question. #1388 pointed
them all at one predicate, and ``test_metrics_single_source`` pins that they agree.
What that leaves undone is *what the predicate actually says* — and the boundary
cases are the usual cause of this class of defect coming back, because the next
surface re-derives them from the name rather than from the code.

The definition, as implemented by ``_apply_owner_and_overdue_filters`` in
``src/api/routes/actions.py`` and exercised below:

    overdue  ==  due_date IS NOT NULL
             AND due_date < now()            -- strictly before, evaluated in SQL
             AND status NOT IN (terminal statuses for that store)

Three consequences worth stating explicitly, because each is a decision rather
than an inevitability:

* **A null due date is not overdue.** An action nobody dated cannot be late. It is
  also not excluded from ``total`` — it is a real action, just an undated one.
* **The comparison is strict.** An action due at this instant is due, not late.
* **"Overdue" is computed, never read.** ``CAPAStatus`` and ``ActionStatus`` both
  have a literal ``overdue`` member, and neither is consulted. A row stamped
  ``overdue`` whose due date is in the future is not counted; a row stamped ``open``
  whose due date has passed is. The stored value is a stale cache of this predicate.

These tests assert deltas around what they seed rather than absolute totals: the
integration schema is not truncated between tests on PostgreSQL, so an absolute
count would be asserting the state of the whole suite.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.incident import (
    ActionStatus,
    Incident,
    IncidentAction,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
)
from src.infrastructure.database import async_session_maker

TENANT = 1
SUMMARY = "/api/v1/actions/summary"


def _aware(days_from_now: float) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days_from_now)


async def _summary(client: AsyncClient) -> dict:
    response = await client.get(SUMMARY)
    assert response.status_code == 200, response.text
    return response.json()


async def _seed_incident_actions(rows: list[tuple[ActionStatus, datetime | None]]) -> None:
    """Seed operational (incident) actions with explicit status/due pairs."""
    tag = uuid.uuid4().hex[:6]
    async with async_session_maker() as session:
        incident = Incident(
            tenant_id=TENANT,
            reference_number=f"INC-ODEF-{tag}",
            title=f"Overdue definition spec {tag}",
            description="Seeded for the overdue definition specification.",
            incident_type=IncidentType.OTHER,
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.PENDING_ACTIONS,
            incident_date=_aware(-40),
            reported_date=_aware(-40),
            created_by_id=1,
        )
        session.add(incident)
        await session.flush()
        for i, (status, due) in enumerate(rows):
            session.add(
                IncidentAction(
                    tenant_id=TENANT,
                    incident_id=incident.id,
                    reference_number=f"IACT-ODEF-{tag}-{i:03d}",
                    title=f"Spec action {tag} {i}",
                    description="Seeded for the overdue definition specification.",
                    status=status,
                    due_date=due,
                    owner_id=1,
                )
            )
        await session.commit()


async def _seed_capa(rows: list[tuple[CAPAStatus, datetime | None]]) -> None:
    """Seed CAPA rows. ``capa_actions.due_date`` is naive, so due dates are stripped."""
    tag = uuid.uuid4().hex[:6]
    async with async_session_maker() as session:
        for i, (status, due) in enumerate(rows):
            session.add(
                CAPAAction(
                    tenant_id=TENANT,
                    reference_number=f"CAPA-ODEF-{tag}-{i:03d}",
                    title=f"Spec CAPA {tag} {i}",
                    description="Seeded for the overdue definition specification.",
                    capa_type=CAPAType.CORRECTIVE,
                    status=status,
                    priority=CAPAPriority.MEDIUM,
                    # MANAGEMENT_REVIEW with a null source_id: the audit-finding
                    # source carries a tenant-scoped partial unique index.
                    source_type=CAPASource.MANAGEMENT_REVIEW,
                    source_id=None,
                    due_date=None if due is None else due.replace(tzinfo=None),
                    created_by_id=1,
                    assigned_to_id=1,
                )
            )
        await session.commit()


class TestTheDueDateBoundary:
    @pytest.mark.asyncio
    async def test_a_past_due_date_is_overdue(self, admin_client: AsyncClient) -> None:
        before = await _summary(admin_client)

        await _seed_incident_actions([(ActionStatus.OPEN, _aware(-1))])

        after = await _summary(admin_client)
        assert after["overdue"] - before["overdue"] == 1

    @pytest.mark.asyncio
    async def test_a_future_due_date_is_not_overdue(self, admin_client: AsyncClient) -> None:
        before = await _summary(admin_client)

        await _seed_incident_actions([(ActionStatus.OPEN, _aware(1))])

        after = await _summary(admin_client)
        assert after["overdue"] - before["overdue"] == 0
        assert after["total"] - before["total"] == 1, "it is still an action"

    @pytest.mark.asyncio
    async def test_the_comparison_is_strict_not_inclusive(self, admin_client: AsyncClient) -> None:
        """An action due imminently is due, not late.

        Seeded a few seconds ahead rather than exactly now: ``now()`` is evaluated
        by the database when the count runs, which is necessarily after the insert,
        so an exact-equality fixture would be a race rather than a boundary.
        """
        before = await _summary(admin_client)

        await _seed_incident_actions([(ActionStatus.OPEN, _aware(0.002))])

        after = await _summary(admin_client)
        assert after["overdue"] - before["overdue"] == 0

    @pytest.mark.asyncio
    async def test_a_null_due_date_is_never_overdue(self, admin_client: AsyncClient) -> None:
        """An action nobody dated cannot be late — but it is still an action."""
        before = await _summary(admin_client)

        await _seed_incident_actions([(ActionStatus.OPEN, None), (ActionStatus.IN_PROGRESS, None)])

        after = await _summary(admin_client)
        assert after["overdue"] - before["overdue"] == 0
        assert after["total"] - before["total"] == 2


class TestTerminalStatusesAreExcluded:
    @pytest.mark.asyncio
    async def test_completed_cancelled_and_verified_operational_actions_are_not_overdue(
        self, admin_client: AsyncClient
    ) -> None:
        """Work that is finished or abandoned is not outstanding, however old."""
        before = await _summary(admin_client)

        await _seed_incident_actions(
            [
                (ActionStatus.COMPLETED, _aware(-30)),
                (ActionStatus.CANCELLED, _aware(-30)),
                (ActionStatus.VERIFIED, _aware(-30)),
            ]
        )

        after = await _summary(admin_client)
        assert after["overdue"] - before["overdue"] == 0
        assert after["total"] - before["total"] == 3

    @pytest.mark.asyncio
    async def test_open_and_in_progress_operational_actions_are_overdue(self, admin_client: AsyncClient) -> None:
        before = await _summary(admin_client)

        await _seed_incident_actions([(ActionStatus.OPEN, _aware(-30)), (ActionStatus.IN_PROGRESS, _aware(-30))])

        after = await _summary(admin_client)
        assert after["overdue"] - before["overdue"] == 2

    @pytest.mark.asyncio
    async def test_a_closed_capa_is_not_overdue_but_one_in_verification_is(self, admin_client: AsyncClient) -> None:
        """``CLOSED`` is the only terminal CAPA status.

        ``VERIFICATION`` means "awaiting verification", i.e. outstanding work, and
        is deliberately counted. This differs from the operational stores, where
        ``VERIFIED`` means verification has happened — the names are close enough to
        be worth pinning so nobody "aligns" them by mistake.
        """
        before = await _summary(admin_client)

        await _seed_capa(
            [
                (CAPAStatus.CLOSED, _aware(-30)),
                (CAPAStatus.VERIFICATION, _aware(-30)),
            ]
        )

        after = await _summary(admin_client)
        assert after["overdue"] - before["overdue"] == 1
        assert after["total"] - before["total"] == 2


class TestOverdueIsComputedNotStored:
    @pytest.mark.asyncio
    async def test_a_row_stamped_overdue_with_a_future_due_date_is_not_counted(self, admin_client: AsyncClient) -> None:
        """The stored ``overdue`` status is a stale cache and is never read.

        Both ``ActionStatus`` and ``CAPAStatus`` carry a literal ``overdue`` member.
        Counting them would double-report rows whose due date has since moved, and
        would report as late a row that a background job has not yet re-stamped.
        """
        before = await _summary(admin_client)

        await _seed_incident_actions([(ActionStatus.OVERDUE, _aware(30))])

        after = await _summary(admin_client)
        assert after["overdue"] - before["overdue"] == 0

    @pytest.mark.asyncio
    async def test_a_row_stamped_open_with_a_past_due_date_is_counted(self, admin_client: AsyncClient) -> None:
        before = await _summary(admin_client)

        await _seed_incident_actions([(ActionStatus.OPEN, _aware(-30))])

        after = await _summary(admin_client)
        assert after["overdue"] - before["overdue"] == 1


class TestOverdueSpansEveryStore:
    @pytest.mark.asyncio
    async def test_one_number_covers_capa_and_operational_actions_alike(self, admin_client: AsyncClient) -> None:
        """ "Overdue" is a property of an action, not of the table it happens to live in.

        The stores disagree about column names — CAPA uses ``assigned_to_id`` and a
        naive ``due_date``, the operational stores use ``owner_id`` and a
        timezone-aware one — and the aggregate has to span them regardless.
        """
        before = await _summary(admin_client)

        await _seed_capa([(CAPAStatus.IN_PROGRESS, _aware(-5))])
        await _seed_incident_actions([(ActionStatus.OPEN, _aware(-5))])

        after = await _summary(admin_client)
        assert after["overdue"] - before["overdue"] == 2
