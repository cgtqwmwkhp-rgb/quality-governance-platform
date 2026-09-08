"""INV-C8 smoke: finding rows satisfy the closure findings gate without a flat string.

This is the gate that blocks complete/close for every user. A run whose findings
exist only as ``investigation_findings`` rows (the C7 editor, or a conversion
that never dual-wrote the flat key) must not be blocked solely for
``MISSING_FINDINGS``. Empty rows plus an empty leftover string must still block.

SQLite-backed so this does not depend on the live API process the other smoke
files exercise. It is the C8-owned smoke; do not weaken the enterprise suite.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.models.investigation import InvestigationRun, InvestigationStatus
from src.domain.models.investigation_finding import InvestigationFinding
from src.domain.services.investigation_closure_helpers import collect_summary_readiness_blockers
from src.domain.services.investigation_service import ClosureReasonCode

TENANT = 7


def _codes(reasons: list) -> list[str]:
    return [c.value if hasattr(c, "value") else str(c) for c in reasons]


@pytest.mark.asyncio
async def test_finding_rows_without_flat_string_are_not_blocked_for_missing_findings():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(InvestigationRun.__table__.create)
        await conn.run_sync(InvestigationFinding.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as db:
            run = InvestigationRun(
                id=1,
                tenant_id=TENANT,
                template_id=1,
                assigned_entity_type="incident",
                assigned_entity_id=42,
                status=InvestigationStatus.IN_PROGRESS,
                title="Fork lift near miss",
                reference_number="INV-C8-SMOKE",
                data={"conclusion": "unsafe system of work", "lead_investigator": "pat@example.com"},
                version=1,
                started_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
                assigned_to_user_id=11,
            )
            db.add(run)
            await db.flush()
            db.add(
                InvestigationFinding(
                    tenant_id=TENANT,
                    investigation_id=int(run.id),
                    sort_order=0,
                    body="Guard was removed before the shift started",
                )
            )
            await db.flush()
            assert not (run.data or {}).get("findings")

            reasons, missing = await collect_summary_readiness_blockers(run, db=db, tenant_id=TENANT)

            assert ClosureReasonCode.MISSING_FINDINGS not in _codes(reasons)
            assert not any(getattr(item, "field_key", None) == "findings" for item in missing)

            empty = InvestigationRun(
                id=2,
                tenant_id=TENANT,
                template_id=1,
                assigned_entity_type="incident",
                assigned_entity_id=43,
                status=InvestigationStatus.IN_PROGRESS,
                title="Empty findings",
                reference_number="INV-C8-SMOKE-EMPTY",
                data={"conclusion": "unsafe system of work", "lead_investigator": "pat@example.com"},
                version=1,
                started_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
                assigned_to_user_id=11,
            )
            db.add(empty)
            await db.flush()
            empty_reasons, _ = await collect_summary_readiness_blockers(empty, db=db, tenant_id=TENANT)
            assert ClosureReasonCode.MISSING_FINDINGS in _codes(empty_reasons)
    finally:
        await engine.dispose()
