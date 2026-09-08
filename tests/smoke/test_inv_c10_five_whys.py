"""INV-C10 smoke: leftover why_1 becomes an analysis without inventing text.

A run whose RCA exists only as leftover ``why_1``..``why_5`` strings (the C4
workspace, or a template run) must convert into ``five_whys_analyses`` on first
read, dual-write those strings, and leave empty Whys empty.

SQLite-backed so this does not depend on the live API process. C10-owned smoke;
do not weaken the enterprise suite.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.models.investigation import InvestigationRun, InvestigationStatus
from src.domain.models.rca_tools import FiveWhysAnalysis
from src.domain.services.investigation_rca_service import InvestigationRcaService

TENANT = 7


@pytest.mark.asyncio
async def test_legacy_why_strings_convert_and_empty_stays_empty():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(InvestigationRun.__table__.create)
        await conn.run_sync(FiveWhysAnalysis.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as db:
            converted = InvestigationRun(
                id=1,
                tenant_id=TENANT,
                template_id=1,
                assigned_entity_type="incident",
                assigned_entity_id=42,
                status=InvestigationStatus.IN_PROGRESS,
                title="Fork lift near miss",
                reference_number="INV-C10-SMOKE",
                data={"why_1": "the interlock was bypassed", "root_cause": "no banksman"},
                version=1,
                started_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
                assigned_to_user_id=11,
            )
            empty = InvestigationRun(
                id=2,
                tenant_id=TENANT,
                template_id=1,
                assigned_entity_type="incident",
                assigned_entity_id=43,
                status=InvestigationStatus.IN_PROGRESS,
                title="Empty RCA",
                reference_number="INV-C10-SMOKE-EMPTY",
                data={},
                version=1,
                started_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
                assigned_to_user_id=11,
            )
            db.add_all([converted, empty])
            await db.flush()

            filled = await InvestigationRcaService.get_workspace(db, investigation=converted, tenant_id=TENANT)
            blank = await InvestigationRcaService.get_workspace(db, investigation=empty, tenant_id=TENANT)

            assert filled["why_1"] == "the interlock was bypassed"
            assert filled["root_cause"] == "no banksman"
            assert filled["whys"][0]["evidence"] == ""
            assert filled["id"] is not None
            assert converted.data["why_1"] == "the interlock was bypassed"

            assert blank["id"] is None
            assert blank["why_1"] == ""
            assert [item["answer"] for item in blank["whys"][:5]] == ["", "", "", "", ""]
            assert await db.scalar(select(func.count(FiveWhysAnalysis.id))) == 1
    finally:
        await engine.dispose()
