"""``GET /api/v1/analytics/kpis`` must not publish hardcoded zeros as measurements (C-7).

The endpoint composed its ``training`` block, and the fallback half of its
``audits`` block, from ``AnalyticsService.get_kpi_summary`` — a method that takes
no session, reads nothing, and returns a literal dict of zeros. #1388 removed that
pattern from the ``actions`` block and left these two in place.

The measured consequence, on the staging database on 29/07/2026: the tenant's
latest training matrix import holds 1932 scored cells of which 1542 were compliant,
i.e. **79.8%**, with 369 lapsed certificates. The endpoint reported
``completion_rate: 0.0`` and ``overdue: 0``. That is not the ambiguous case of a
stub zero being indistinguishable from a real zero — it was flatly contradicting
the database.

Two shapes are asserted below, and the distinction is the whole point:

* A figure that **was** measured keeps reporting exactly what it found, including
  a genuine 0.0 when nothing is compliant.
* A figure that **could not** be measured is not expressible as a number at all.
  ``status: "unavailable"`` carries no ``completion_rate`` key, because the web
  client reads this payload and the ``?? 0`` idiom would otherwise put the
  fabricated zero straight back (the trap #1404 documented).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Annotated, Optional

import pytest
from fastapi import Depends
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import get_current_user
from src.domain.models.training_matrix import (
    TrainingMatrixCell,
    TrainingMatrixCourse,
    TrainingMatrixImport,
    TrainingMatrixPerson,
)
from src.domain.models.user import User
from src.domain.services.audit_analytics_service import AuditAnalyticsService
from src.infrastructure.database import async_session_maker, get_db
from src.main import app

KPIS = "/api/v1/analytics/kpis"
TENANT = 1


async def _request_session_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Load the current user on the request session, as production does.

    Mirrors ``test_analytics_kpis_endpoint``: the default harness loads the user on
    a separate session, which hides the interaction between a dashboard rollback
    and an expired ``current_user``.
    """
    result = await db.execute(select(User).where(User.id == 1).options(selectinload(User.roles)))
    return result.scalar_one()


@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[get_current_user] = _request_session_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def failing_audit_summary(monkeypatch):
    """Make the audit aggregate fail with a real DB error, as schema drift does.

    Patched at ``AuditAnalyticsService.get_summary`` rather than at the dashboard
    method that wraps it, because that is the one point **both** the old and new
    handlers go through. Patching the wrapper would leave the old handler's second,
    direct call to this service working, and the tests below would then pass against
    the defect they exist to catch.

    A ``text()`` statement against a missing column is used rather than a bare
    ``raise`` so the transaction is genuinely aborted. That is what makes this
    fixture able to tell a rollback-safe handler from one that merely swallows.
    """

    async def _boom(self, tenant_id, days=30):
        await self.db.execute(text("SELECT column_that_does_not_exist FROM tenants"))
        raise AssertionError("unreachable: the statement above must fail")

    monkeypatch.setattr(AuditAnalyticsService, "get_summary", _boom)


async def _seed_training_import(
    *,
    scored_compliant: int,
    scored_lapsed: int,
    unscored: int,
    expiring_in_days: Optional[int] = None,
) -> int:
    """Seed a fresh training matrix import and return the number of scored cells.

    The aggregate reads only the tenant's most recent import, so seeding a new one
    makes the denominator exactly what this function put in it. That matters on
    PostgreSQL, where the integration schema is not truncated between tests and an
    absolute count would otherwise be asserting the state of the whole suite.
    """
    tag = uuid.uuid4().hex[:8]
    today = date.today()
    async with async_session_maker() as session:
        imp = TrainingMatrixImport(
            tenant_id=TENANT,
            filename=f"c7-{tag}.csv",
            status="completed",
        )
        session.add(imp)
        person = TrainingMatrixPerson(tenant_id=TENANT, atlas_name=f"C7 Person {tag}")
        session.add(person)

        # (passed_on, expires_on) for each cell this import should hold.
        wanted: list[tuple[Optional[date], Optional[date]]] = []
        wanted += [(today - timedelta(days=400), today + timedelta(days=365))] * scored_compliant
        wanted += [(today - timedelta(days=800), today - timedelta(days=10))] * scored_lapsed
        wanted += [(None, None)] * unscored
        if expiring_in_days is not None:
            wanted.append((today - timedelta(days=300), today + timedelta(days=expiring_in_days)))

        # A unique constraint covers (tenant, import, person, course), so each cell
        # needs its own course rather than a second row against a shared one.
        courses = [
            TrainingMatrixCourse(
                tenant_id=TENANT,
                course_key=f"c7-course-{tag}-{seq}",
                display_name=f"C7 Course {tag} {seq}",
            )
            for seq in range(len(wanted))
        ]
        session.add_all(courses)
        await session.flush()

        session.add_all(
            [
                TrainingMatrixCell(
                    tenant_id=TENANT,
                    import_id=imp.id,
                    person_id=person.id,
                    course_id=course.id,
                    passed_on=passed_on,
                    expires_on=expires_on,
                )
                for course, (passed_on, expires_on) in zip(courses, wanted)
            ]
        )
        await session.commit()

    return scored_compliant + scored_lapsed + (1 if expiring_in_days is not None else 0)


async def _kpis(client: AsyncClient) -> dict:
    response = await client.get(KPIS)
    assert response.status_code == 200, response.text
    return response.json()


class TestTrainingWasMeasured:
    """A figure taken from the matrix reports what the matrix holds."""

    @pytest.mark.asyncio
    async def test_completion_rate_matches_the_seeded_matrix(self, admin_client: AsyncClient) -> None:
        """The regression that matters: a populated matrix used to read 0.0%."""
        await _seed_training_import(scored_compliant=3, scored_lapsed=1, unscored=5)

        training = (await _kpis(admin_client))["training"]

        assert training["status"] == "measured"
        # 3 of 4 scored cells compliant. The 5 unscored cells are an unpopulated
        # requirement, not a failure, so they stay out of the denominator.
        assert training["measured_cells"] == 4
        assert training["compliant_cells"] == 3
        assert training["completion_rate"] == 75.0

    @pytest.mark.asyncio
    async def test_lapsed_certificates_are_counted_as_overdue(self, admin_client: AsyncClient) -> None:
        await _seed_training_import(scored_compliant=2, scored_lapsed=3, unscored=0)

        training = (await _kpis(admin_client))["training"]

        assert training["overdue"] == 3
        assert training["expiring_soon"] == 0

    @pytest.mark.asyncio
    async def test_an_expiry_inside_the_horizon_is_expiring_soon(self, admin_client: AsyncClient) -> None:
        await _seed_training_import(scored_compliant=1, scored_lapsed=0, unscored=0, expiring_in_days=10)

        training = (await _kpis(admin_client))["training"]

        # Still compliant — it has not expired — but flagged as needing renewal.
        assert training["expiring_soon"] == 1
        assert training["overdue"] == 0
        assert training["completion_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_a_genuine_zero_is_still_reported_as_zero(self, admin_client: AsyncClient) -> None:
        """The fix narrows what 0.0 may mean; it does not stop it meaning anything.

        A matrix whose every scored cell has lapsed really is 0% compliant, and
        that has to keep arriving as a number rather than as "unavailable".
        """
        await _seed_training_import(scored_compliant=0, scored_lapsed=4, unscored=0)

        training = (await _kpis(admin_client))["training"]

        assert training["status"] == "measured"
        assert training["completion_rate"] == 0.0
        assert training["measured_cells"] == 4


class TestTrainingCouldNotBeMeasured:
    """The defect: an unmeasurable figure arriving as a confident zero."""

    @pytest.mark.asyncio
    async def test_a_matrix_with_no_scored_cell_is_not_a_measurement(self, admin_client: AsyncClient) -> None:
        await _seed_training_import(scored_compliant=0, scored_lapsed=0, unscored=6)

        training = (await _kpis(admin_client))["training"]

        assert training["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_no_number_is_offered_when_nothing_was_measured(self, admin_client: AsyncClient) -> None:
        """No numeric key at all, not a null one.

        The web client read ``Number(payload?.training?.completion_rate ?? 0)``, so
        a ``completion_rate`` of any kind — 0, null, or absent-from-a-200 — was
        indistinguishable from a measured 0%. Omitting the key does not fix the
        client on its own, which is why ``status`` is present for it to branch on,
        but publishing a number here would make the client's honesty impossible.
        """
        await _seed_training_import(scored_compliant=0, scored_lapsed=0, unscored=6)

        training = (await _kpis(admin_client))["training"]

        for numeric_field in ("completion_rate", "expiring_soon", "overdue", "compliant_cells", "measured_cells"):
            assert numeric_field not in training, f"unmeasurable training still offered {numeric_field}: {training!r}"

    @pytest.mark.asyncio
    async def test_the_unavailable_branch_names_what_is_missing(self, admin_client: AsyncClient) -> None:
        """An operator needs to know it is the matrix, not the endpoint, that is absent."""
        await _seed_training_import(scored_compliant=0, scored_lapsed=0, unscored=6)

        training = (await _kpis(admin_client))["training"]

        assert training["reason"] == "no_scored_training_matrix_cells"
        assert "training matrix" in training["detail"]

    @pytest.mark.asyncio
    async def test_measured_and_unmeasurable_are_not_interchangeable(self, admin_client: AsyncClient) -> None:
        """The whole point: these two must not arrive as the same answer."""
        await _seed_training_import(scored_compliant=0, scored_lapsed=4, unscored=0)
        real_zero = (await _kpis(admin_client))["training"]

        await _seed_training_import(scored_compliant=0, scored_lapsed=0, unscored=4)
        unmeasurable = (await _kpis(admin_client))["training"]

        assert real_zero != unmeasurable
        assert real_zero["completion_rate"] == 0.0
        assert "completion_rate" not in unmeasurable


class TestTrainingIsNotAStub:
    """Guards against the specific mechanism, not just the current symptom."""

    @pytest.mark.asyncio
    async def test_the_block_does_not_carry_the_stub_shape(self, admin_client: AsyncClient) -> None:
        """``AnalyticsService.get_kpi_summary`` returned exactly three keys.

        Pinning the shape means rewiring that stub back in fails here rather than
        going unnoticed, whatever the numbers happen to be at the time.
        """
        await _seed_training_import(scored_compliant=2, scored_lapsed=0, unscored=0)

        training = (await _kpis(admin_client))["training"]

        assert set(training) != {"completion_rate", "expiring_soon", "overdue"}
        assert "status" in training

    @pytest.mark.asyncio
    async def test_the_kpi_tile_agrees_with_the_dashboard_it_projects(self, admin_client: AsyncClient) -> None:
        """One measurement, two surfaces — the invariant #1388 established."""
        await _seed_training_import(scored_compliant=3, scored_lapsed=1, unscored=2)

        kpi_training = (await _kpis(admin_client))["training"]
        dashboard = await admin_client.get("/api/v1/executive-dashboard?period_days=30")
        assert dashboard.status_code == 200, dashboard.text
        dash_training = dashboard.json()["training"]

        assert kpi_training["completion_rate"] == dash_training["completion_rate"]
        assert kpi_training["measured_cells"] == dash_training["measured_cells"]
        assert kpi_training["overdue"] == dash_training["overdue"]


class TestAuditsDoNotFallBackToStubZeros:
    """The audits half of C-7: a failed query used to publish the stub's zeros."""

    @pytest.mark.asyncio
    async def test_a_failed_audit_query_does_not_report_a_zero_score(
        self, admin_client: AsyncClient, failing_audit_summary
    ) -> None:
        """``avg_score`` was 0.0 from the stub — a fabricated 0% audit result.

        This is the assertion that bites. Under the old handler the stub seeded
        ``avg_score: 0.0`` and the ``except: pass`` left it in place, so a broken
        audit aggregate published a confident zero score.
        """
        audits = (await _kpis(admin_client))["audits"]

        assert audits["avg_score"] is None
        assert audits["pass_rate"] is None
        assert audits["essential_compliance_pct"] is None

    @pytest.mark.asyncio
    async def test_a_failed_audit_query_does_not_report_a_zero_trend(
        self, admin_client: AsyncClient, failing_audit_summary
    ) -> None:
        """The stub's ``trend: 0.0`` rendered as a green "no change" indicator."""
        audits = (await _kpis(admin_client))["audits"]

        assert audits["trend"] is None

    @pytest.mark.asyncio
    async def test_the_endpoint_still_degrades_rather_than_500ing(
        self, admin_client: AsyncClient, failing_audit_summary
    ) -> None:
        """Removing the swallow must not turn a broken tile into a broken page.

        The aborted transaction is rolled back by ``_safe_call``, so the aggregates
        that run after it still return real numbers. Without a rollback PostgreSQL
        would refuse every subsequent statement in the request.

        Not a regression test: this passes on the pre-fix handler too, because
        nothing in it queried after the swallow. It is a guard on the new ordering,
        which does put queries after a possible rollback.
        """
        body = await _kpis(admin_client)

        assert body["source"] == "executive_dashboard"
        assert isinstance(body["actions"]["total"], int)
        assert isinstance(body["incidents"]["total"], int)

    @pytest.mark.asyncio
    async def test_audit_trend_is_never_a_fabricated_zero(self, admin_client: AsyncClient) -> None:
        """Also true on the success path: no audit trend is computed anywhere."""
        audits = (await _kpis(admin_client))["audits"]

        assert audits["trend"] is None

    @pytest.mark.asyncio
    async def test_the_audit_block_agrees_with_the_dashboard(self, admin_client: AsyncClient) -> None:
        """Single source: the projection cannot contradict the aggregate.

        Also passes pre-fix, because on the success path the old handler's second
        query returned the same numbers the dashboard had already computed. Kept as
        the invariant that stops the two drifting apart again, not as evidence.
        """
        kpi_audits = (await _kpis(admin_client))["audits"]
        dashboard = await admin_client.get("/api/v1/executive-dashboard?period_days=30")
        assert dashboard.status_code == 200, dashboard.text
        dash_audits = dashboard.json()["audits"]

        assert kpi_audits["total"] == dash_audits["totals"]
        assert kpi_audits["completed"] == dash_audits["completed"]
        assert kpi_audits["avg_score"] == dash_audits["avg_score"]
