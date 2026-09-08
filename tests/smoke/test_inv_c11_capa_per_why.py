"""INV-C11 smoke: empty Why does not invent a CAPA; a filled Why links.

SQLite-backed so this does not depend on the live API process.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.exceptions import ValidationError
from src.domain.models.capa import CAPAAction
from src.domain.models.investigation import InvestigationRun, InvestigationStatus
from src.domain.models.rca_tools import FiveWhysAnalysis
from src.domain.services.capa_service import CAPAService

TENANT = 7


@pytest.mark.asyncio
async def test_empty_why_invents_no_capa_and_filled_why_links():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(InvestigationRun.__table__.create)
        await conn.run_sync(FiveWhysAnalysis.__table__.create)
        await conn.run_sync(CAPAAction.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as db:
            empty = InvestigationRun(
                id=1,
                tenant_id=TENANT,
                template_id=1,
                assigned_entity_type="incident",
                assigned_entity_id=42,
                status=InvestigationStatus.IN_PROGRESS,
                title="Empty Why",
                reference_number="INV-C11-EMPTY",
                data={},
                version=1,
                started_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
                assigned_to_user_id=11,
            )
            filled = InvestigationRun(
                id=2,
                tenant_id=TENANT,
                template_id=1,
                assigned_entity_type="incident",
                assigned_entity_id=43,
                status=InvestigationStatus.IN_PROGRESS,
                title="Filled Why",
                reference_number="INV-C11-FILLED",
                data={"why_1": "the interlock was bypassed"},
                version=1,
                started_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
                assigned_to_user_id=11,
            )
            db.add_all([empty, filled])
            db.add(
                FiveWhysAnalysis(
                    tenant_id=TENANT,
                    investigation_id=1,
                    problem_statement="",
                    whys=[],
                    created_by_id=11,
                    updated_by_id=11,
                )
            )
            db.add(
                FiveWhysAnalysis(
                    tenant_id=TENANT,
                    investigation_id=2,
                    problem_statement="fork lift",
                    whys=[{"level": 1, "why": "", "answer": "the interlock was bypassed", "evidence": None}],
                    created_by_id=11,
                    updated_by_id=11,
                )
            )
            await db.flush()

            svc = CAPAService(db)
            with (
                patch(
                    "src.domain.services.capa_service.ReferenceNumberService.generate",
                    new=AsyncMock(return_value="CAPA-2026-0113"),
                ),
                patch("src.domain.services.capa_service.record_audit_event", new=AsyncMock()),
                patch("src.domain.services.capa_service.invalidate_tenant_cache", new=AsyncMock()),
                patch("src.domain.services.capa_service.track_metric"),
            ):
                with pytest.raises(ValidationError, match="not invented"):
                    await svc.create_capa_from_why(1, user_id=11, tenant_id=TENANT, why_level=1)
                capa = await svc.create_capa_from_why(2, user_id=11, tenant_id=TENANT, why_level=1)

            assert capa.why_level == 1
            assert capa.five_whys_id is not None
            assert "the interlock was bypassed" in (capa.title or "")
            assert await db.scalar(select(func.count(CAPAAction.id))) == 1
    finally:
        await engine.dispose()
