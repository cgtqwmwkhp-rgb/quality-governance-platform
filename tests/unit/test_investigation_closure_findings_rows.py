"""INV-C8: the closure gate reads finding rows, not the flat JSON key.

C7 stored findings as rows and still dual-wrote the concatenated string because
this gate (and the pack) read ``data["findings"]``. A run whose findings lived
only as rows — or only nested under ``data.sections`` from INV-C4 — was blocked
from complete/close, and a run whose string was stale could close incorrectly.

The gate now asks "is there at least one non-empty ``investigation_findings``
row for this tenant?". Empty rows plus an empty leftover string stay
MISSING_FINDINGS. A leftover string is converted once through C7's splitter;
nothing is invented.

SQLite-backed: only ``investigation_runs`` and ``investigation_findings`` are
created, the same shape as the C7 row tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.models.investigation import InvestigationRun, InvestigationStatus
from src.domain.models.investigation_finding import InvestigationFinding
from src.domain.services.investigation_closure_helpers import collect_summary_readiness_blockers
from src.domain.services.investigation_findings_service import InvestigationFindingsService
from src.domain.services.investigation_service import ClosureReasonCode

TENANT = 7
OTHER_TENANT = 9
FINDINGS_SECTION = "section_3_investigation_findings"


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(InvestigationRun.__table__.create)
        await conn.run_sync(InvestigationFinding.__table__.create)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


async def _run(db: AsyncSession, *, run_id: int = 1, tenant_id: int = TENANT, data=None) -> InvestigationRun:
    run = InvestigationRun(
        id=run_id,
        tenant_id=tenant_id,
        template_id=1,
        assigned_entity_type="incident",
        assigned_entity_id=42 + run_id,
        status=InvestigationStatus.IN_PROGRESS,
        title="Fork lift near miss",
        reference_number=f"INV-{run_id}",
        data={} if data is None else data,
        version=1,
        started_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        assigned_to_user_id=11,
    )
    db.add(run)
    await db.flush()
    return run


async def _add_row(
    db: AsyncSession,
    *,
    investigation: InvestigationRun,
    body: str,
    tenant_id: int | None = None,
    sort_order: int = 0,
) -> InvestigationFinding:
    """Insert a finding row *without* C7's JSON sync — the C8 defect shape."""
    row = InvestigationFinding(
        tenant_id=TENANT if tenant_id is None else tenant_id,
        investigation_id=int(investigation.id),
        sort_order=sort_order,
        body=body,
    )
    db.add(row)
    await db.flush()
    return row


def _codes(reasons: list) -> list[str]:
    return [c.value if hasattr(c, "value") else str(c) for c in reasons]


@pytest.mark.asyncio
async def test_a_finding_row_satisfies_the_gate_when_the_flat_key_is_empty(session_factory):
    """The defect: rows existed, ``data.findings`` did not, complete was blocked."""
    async with session_factory() as db:
        run = await _run(db, data={"conclusion": "unsafe system of work", "lead_investigator": "pat@example.com"})
        await _add_row(db, investigation=run, body="Guard was removed")
        assert "findings" not in (run.data or {})

        reasons, missing = await collect_summary_readiness_blockers(run, db=db, tenant_id=TENANT)

        assert ClosureReasonCode.MISSING_FINDINGS not in _codes(reasons)
        assert not any(getattr(item, "field_key", None) == "findings" for item in missing)


@pytest.mark.asyncio
async def test_empty_rows_and_empty_string_still_block(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"conclusion": "unsafe system of work", "lead_investigator": "pat@example.com"})

        reasons, missing = await collect_summary_readiness_blockers(run, db=db, tenant_id=TENANT)

        assert ClosureReasonCode.MISSING_FINDINGS in _codes(reasons)
        assert any(getattr(item, "field_key", None) == "findings" for item in missing)


@pytest.mark.asyncio
async def test_whitespace_only_row_does_not_count_as_a_finding(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"findings": "   "})
        await _add_row(db, investigation=run, body="   ")

        reasons, _missing = await collect_summary_readiness_blockers(run, db=db, tenant_id=TENANT)

        assert ClosureReasonCode.MISSING_FINDINGS in _codes(reasons)


@pytest.mark.asyncio
async def test_nested_only_legacy_converts_then_passes(session_factory):
    """INV-C4 could leave findings only under sections; C7's reader still sees them."""
    async with session_factory() as db:
        run = await _run(
            db,
            data={"sections": {FINDINGS_SECTION: {"findings": "Guard was removed", "conclusion": "keep"}}},
        )

        reasons, _missing = await collect_summary_readiness_blockers(run, db=db, tenant_id=TENANT)

        assert ClosureReasonCode.MISSING_FINDINGS not in _codes(reasons)
        rows = await InvestigationFindingsService._ordered_rows(  # noqa: SLF001
            db, investigation_id=int(run.id), tenant_id=TENANT
        )
        assert [row.body for row in rows] == ["Guard was removed"]
        # Conversion keeps the pack's string in step; it does not invent wording.
        assert run.data["findings"] == "Guard was removed"


@pytest.mark.asyncio
async def test_a_stale_flat_string_does_not_pass_when_rows_are_empty(session_factory):
    """Deleting every finding rewrites the string to empty; a leftover string
    would only pass if conversion still saw it. After delete, both are empty."""
    async with session_factory() as db:
        run = await _run(db, data={"findings": "Guard was removed"})
        rows = await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT)
        await InvestigationFindingsService.delete_finding(
            db, investigation=run, tenant_id=TENANT, finding_id=rows[0].id
        )
        assert run.data["findings"] == ""

        reasons, _missing = await collect_summary_readiness_blockers(run, db=db, tenant_id=TENANT)

        assert ClosureReasonCode.MISSING_FINDINGS in _codes(reasons)


@pytest.mark.asyncio
async def test_another_tenants_rows_do_not_satisfy_the_gate(session_factory):
    async with session_factory() as db:
        ours = await _run(db, run_id=1, tenant_id=TENANT, data={})
        theirs = await _run(db, run_id=2, tenant_id=OTHER_TENANT, data={})
        await _add_row(db, investigation=theirs, body="their finding", tenant_id=OTHER_TENANT)

        reasons, _missing = await collect_summary_readiness_blockers(ours, db=db, tenant_id=TENANT)

        assert ClosureReasonCode.MISSING_FINDINGS in _codes(reasons)
        assert (
            await InvestigationFindingsService.has_non_empty_findings(db, investigation=theirs, tenant_id=TENANT)
            is False
        )


@pytest.mark.asyncio
async def test_a_mismatched_tenant_id_fails_closed_even_when_rows_exist(session_factory):
    """The probe scope is the run's tenant. Asking as another tenant must not pass."""
    async with session_factory() as db:
        run = await _run(db, data={})
        await _add_row(db, investigation=run, body="Guard was removed")

        reasons, _missing = await collect_summary_readiness_blockers(run, db=db, tenant_id=OTHER_TENANT)

        assert ClosureReasonCode.MISSING_FINDINGS in _codes(reasons)
        # And it must not have converted/copied the row into the other tenant.
        other_rows = await InvestigationFindingsService._ordered_rows(  # noqa: SLF001
            db, investigation_id=int(run.id), tenant_id=OTHER_TENANT
        )
        assert other_rows == []


@pytest.mark.asyncio
async def test_a_probe_error_fails_closed_rather_than_raising(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"findings": "Guard was removed"})
        db_broken = AsyncMock()
        db_broken.execute = AsyncMock(side_effect=RuntimeError("findings table unreachable"))

        reasons, missing = await collect_summary_readiness_blockers(run, db=db_broken, tenant_id=TENANT)

        assert ClosureReasonCode.MISSING_FINDINGS in _codes(reasons)
        assert any(getattr(item, "field_key", None) == "findings" for item in missing)


@pytest.mark.asyncio
async def test_has_non_empty_findings_does_not_invent_from_blank_legacy(session_factory):
    async with session_factory() as db:
        run = await _run(db, data={"findings": "   ", "conclusion": "unsafe system of work"})

        assert (
            await InvestigationFindingsService.has_non_empty_findings(db, investigation=run, tenant_id=TENANT) is False
        )
        assert await InvestigationFindingsService.list_findings(db, investigation=run, tenant_id=TENANT) == []
        assert run.data["findings"] == "   "
