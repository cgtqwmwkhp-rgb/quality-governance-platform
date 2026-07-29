"""A broken audit aggregate must not publish a zero audit count (C-7).

``test_analytics_kpis_stub_zeros`` covers this endpoint against the shared schema
with ``AuditAnalyticsService.get_summary`` monkeypatched to fail. That establishes
the *rates* are honest — ``avg_score``, ``pass_rate`` and
``essential_compliance_pct`` all arrive as None rather than 0.0.

It does not cover the counts, and the counts were the residual. ``total``,
``completed`` and ``in_progress`` came from the aggregate's empty default and
arrived as ``0``, which is byte-identical to a tenant that genuinely ran no
audits. A director reading "0 audits" cannot tell that from "we could not read
your audits".

What makes that a fabrication rather than an approximation is visible only
against real drift, which is why this file exists alongside the monkeypatched
one. ``AuditAnalyticsService.get_summary`` counts rows *before* it filters on
status, so with ``audit_runs.status`` dropped:

    SELECT count(*) FROM audit_runs WHERE tenant_id = 1     -- succeeds, returns 3
    SELECT ... WHERE tenant_id = 1 AND status = 'completed' -- fails, column gone

The endpoint had already successfully read the number 3 when it published 0. The
zero was not a degraded estimate of the total; it was unrelated to a total the
process was holding. A monkeypatched ``raise`` cannot reproduce that asymmetry
because it fails the whole method at once.

Measured on the drifted database before the fix, with 3 runs seeded:

    audits: {"total": 0, "completed": 0, "in_progress": 0, "avg_score": null, ...}

and after:

    audits: {"status": "unavailable", "reason": "audit_aggregate_query_failed", ...}
"""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

from tests.integration._fabricated_zero_scratch import AUDIT_RUNS_STATUS, is_postgres

KPIS = "/api/v1/analytics/kpis"

pytestmark = pytest.mark.skipif(
    not is_postgres(os.environ.get("DATABASE_URL", "")),
    reason=(
        "the asymmetry under test — a count that succeeds followed by one that "
        "fails on the same table — needs real DROP COLUMN against PostgreSQL."
    ),
)


async def _audits(client: AsyncClient) -> dict:
    response = await client.get(KPIS)
    assert response.status_code == 200, response.text
    return response.json()["audits"]


class TestAuditsWereMeasured:
    """Baseline, so the unavailable assertions below cannot pass vacuously."""

    @pytest.mark.asyncio
    async def test_an_undrifted_schema_reports_the_seeded_runs(
        self, drifted_scratch, drifted_scratch_client: AsyncClient
    ) -> None:
        await drifted_scratch.seed_audit_runs(completed=2, in_progress=1)

        audits = await _audits(drifted_scratch_client)

        assert audits["status"] == "measured"
        assert audits["total"] == 3
        assert audits["completed"] == 2
        assert audits["avg_score"] == 90.0

    @pytest.mark.asyncio
    async def test_a_tenant_with_no_audits_reports_a_real_zero(self, drifted_scratch_client: AsyncClient) -> None:
        """The measured-zero case must keep arriving as a number.

        The fix narrows what 0 may mean. It must not stop a genuine "you have run
        no audits" from being expressible, or the tile becomes useless for the
        tenants who most need to see it.
        """
        audits = await _audits(drifted_scratch_client)

        assert audits["status"] == "measured"
        assert audits["total"] == 0
        assert audits["completed"] == 0


class TestAuditsCouldNotBeMeasured:
    """The residual: a readable table published as zero."""

    @pytest.mark.asyncio
    async def test_a_broken_aggregate_does_not_report_zero_audits(
        self, drifted_scratch, drifted_scratch_client: AsyncClient
    ) -> None:
        """The assertion that bites. Pre-fix: ``status`` absent, ``total`` 0, with 3 runs in the table."""
        await drifted_scratch.seed_audit_runs(completed=2, in_progress=1)
        await drifted_scratch.drop_column(*AUDIT_RUNS_STATUS)
        assert not await drifted_scratch.has_column(*AUDIT_RUNS_STATUS), "the drift did not take"

        audits = await _audits(drifted_scratch_client)

        assert audits["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_no_count_is_offered_when_the_aggregate_failed(
        self, drifted_scratch, drifted_scratch_client: AsyncClient
    ) -> None:
        """Omitted, not nulled.

        The web client read ``Number(payload?.audits?.total ?? 0)``, and
        ``null ?? 0`` is 0 — so a nullable ``total`` would leave the fabricated
        zero one defensive idiom away from returning. Absence is the only shape
        that idiom cannot silently convert into a measurement.
        """
        await drifted_scratch.seed_audit_runs(completed=2, in_progress=1)
        await drifted_scratch.drop_column(*AUDIT_RUNS_STATUS)

        audits = await _audits(drifted_scratch_client)

        for count_field in ("total", "completed", "in_progress", "incomplete_critical_count"):
            assert count_field not in audits, f"unmeasurable audits still offered {count_field}: {audits!r}"

    @pytest.mark.asyncio
    async def test_the_unavailable_branch_names_what_broke(
        self, drifted_scratch, drifted_scratch_client: AsyncClient
    ) -> None:
        await drifted_scratch.seed_audit_runs(completed=1, in_progress=0)
        await drifted_scratch.drop_column(*AUDIT_RUNS_STATUS)

        audits = await _audits(drifted_scratch_client)

        assert audits["reason"] == "audit_aggregate_query_failed"
        assert "not a report that there are no audits" in audits["detail"]

    @pytest.mark.asyncio
    async def test_measured_zero_and_unmeasurable_are_not_interchangeable(
        self, drifted_scratch, drifted_scratch_client: AsyncClient
    ) -> None:
        """Read the same tile twice, once honestly empty and once unreadable."""
        real_zero = await _audits(drifted_scratch_client)

        await drifted_scratch.seed_audit_runs(completed=2, in_progress=1)
        await drifted_scratch.drop_column(*AUDIT_RUNS_STATUS)
        unmeasurable = await _audits(drifted_scratch_client)

        assert real_zero != unmeasurable
        assert real_zero["total"] == 0
        assert "total" not in unmeasurable

    @pytest.mark.asyncio
    async def test_the_rest_of_the_page_still_reports(
        self, drifted_scratch, drifted_scratch_client: AsyncClient
    ) -> None:
        """One broken tile must not cost the other eleven.

        The aborted transaction has to be unwound for the aggregates that run
        after audits to return anything at all, so this is a guard on the
        savepoint scoping as much as on the tile.
        """
        await drifted_scratch.seed_audit_runs(completed=2, in_progress=1)
        await drifted_scratch.seed_incident_actions(2)
        await drifted_scratch.drop_column(*AUDIT_RUNS_STATUS)

        response = await drifted_scratch_client.get(KPIS)
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["audits"]["status"] == "unavailable"
        assert isinstance(body["incidents"]["total"], int)
        assert isinstance(body["actions"]["total"], int)
