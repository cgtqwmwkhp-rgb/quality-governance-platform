"""Integration tests for AuditAnalyticsService and the essential-fail completion
gate, against an isolated in-memory SQLite database (mirrors the pattern used
by tests/integration/test_audit_version_entity_integrity.py).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.models.asset import Asset, AssetType, TemplateAssetType
from src.domain.models.audit import (
    AuditFinding,
    AuditQuestion,
    AuditResponse,
    AuditRun,
    AuditSection,
    AuditStatus,
    AuditTemplate,
    FindingStatus,
    audit_finding_risks,
)
from src.domain.models.engineer import Engineer
from src.domain.models.location import Location
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.models.user import User
from src.domain.services.audit_analytics_service import AuditAnalyticsService
from src.domain.services.audit_service import AuditService
from tests.conftest import generate_test_reference


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        for table in (
            User.__table__,
            AssetType.__table__,
            Asset.__table__,
            Location.__table__,
            Engineer.__table__,
            AuditTemplate.__table__,
            AuditSection.__table__,
            AuditQuestion.__table__,
            AuditRun.__table__,
            AuditResponse.__table__,
            AuditFinding.__table__,
            TemplateAssetType.__table__,
            EnterpriseRisk.__table__,
            audit_finding_risks,
        ):
            await conn.run_sync(table.create)

    async with session_factory() as session:
        yield session

    await engine.dispose()


TENANT_ID = 1


async def _seed_template_with_essential_question(db: AsyncSession, *, question_type="pass_fail") -> AuditTemplate:
    template = AuditTemplate(
        name="Forklift Safety",
        reference_number=generate_test_reference("TPL"),
        tenant_id=TENANT_ID,
        is_published=True,
        passing_score=70,
    )
    db.add(template)
    await db.flush()
    section = AuditSection(template_id=template.id, title="Safety checks", sort_order=0, weight=1.0)
    db.add(section)
    await db.flush()
    question = AuditQuestion(
        template_id=template.id,
        section_id=section.id,
        question_text="Are the brakes fully functional?",
        question_type=question_type,
        weight=1.0,
        max_score=1.0,
        is_required=True,
        criticality="essential",
    )
    db.add(question)
    await db.flush()
    await db.commit()
    return template


async def _make_run(
    db: AsyncSession,
    template: AuditTemplate,
    *,
    status: AuditStatus,
    asset_type_id: int | None = None,
) -> AuditRun:
    run = AuditRun(
        template_id=template.id,
        template_version=1,
        status=status,
        tenant_id=TENANT_ID,
        reference_number=f"AUD-{template.id}-{status.value}",
        asset_type_id=asset_type_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()
    return run


@pytest.mark.asyncio
async def test_get_summary_reports_essential_compliance_and_pass_rate(db: AsyncSession):
    from sqlalchemy import select

    template = await _seed_template_with_essential_question(db)
    result = await db.execute(select(AuditQuestion).where(AuditQuestion.template_id == template.id))
    question = result.scalars().first()

    completed_run = await _make_run(db, template, status=AuditStatus.COMPLETED)
    completed_run.score = 1.0
    completed_run.max_score = 1.0
    completed_run.score_percentage = 100.0
    completed_run.passed = True
    db.add(
        AuditResponse(
            run_id=completed_run.id,
            question_id=question.id,
            response_value="fail",
            score=0.0,
            max_score=1.0,
            applicability="applicable",
        )
    )
    db.add(
        AuditFinding(
            run_id=completed_run.id,
            question_id=question.id,
            title="Brakes not functional",
            description="Observed defective brakes",
            severity="high",
            status=FindingStatus.OPEN,
            tenant_id=TENANT_ID,
            reference_number=generate_test_reference("FND"),
        )
    )
    await db.commit()

    service = AuditAnalyticsService(db)
    summary = await service.get_summary(TENANT_ID, days=365)

    assert summary["totals"] == 1
    assert summary["completed"] == 1
    assert summary["in_progress"] == 0
    assert summary["avg_score"] == 100.0
    # essential_compliance_pct reflects the failed essential response regardless
    # of the run's own `passed` flag (proxy signal independent of run.passed).
    assert summary["essential_compliance_pct"] == 0.0


@pytest.mark.asyncio
async def test_get_dimensions_group_by_asset_type(db: AsyncSession):
    template = await _seed_template_with_essential_question(db)
    asset_type = AssetType(category="lifting", name="Forklift", tenant_id=TENANT_ID)
    db.add(asset_type)
    await db.flush()

    run_a = await _make_run(db, template, status=AuditStatus.COMPLETED, asset_type_id=asset_type.id)
    run_a.score_percentage = 90.0
    run_a.passed = True
    run_b = await _make_run(db, template, status=AuditStatus.IN_PROGRESS, asset_type_id=asset_type.id)
    await db.commit()

    service = AuditAnalyticsService(db)
    dims = await service.get_dimensions(TENANT_ID, group_by="asset_type", days=365)

    assert len(dims) == 1
    assert dims[0]["key"] == str(asset_type.id)
    assert dims[0]["label"] == "Forklift"
    assert dims[0]["run_count"] == 2
    assert dims[0]["completed_count"] == 1
    assert dims[0]["avg_score"] == 90.0
    assert run_b.id  # keep reference alive for lints


@pytest.mark.asyncio
async def test_get_critical_queue_lists_unanswered_essential_item(db: AsyncSession):
    template = await _seed_template_with_essential_question(db)
    await _make_run(db, template, status=AuditStatus.IN_PROGRESS)
    await db.commit()

    service = AuditAnalyticsService(db)
    queue = await service.get_critical_queue(TENANT_ID)

    assert len(queue) == 1
    assert queue[0].reason == "unanswered"
    assert queue[0].template_name == "Forklift Safety"


@pytest.mark.asyncio
async def test_get_critical_queue_lists_failed_open_finding(db: AsyncSession):
    from sqlalchemy import select

    template = await _seed_template_with_essential_question(db)
    result = await db.execute(select(AuditQuestion).where(AuditQuestion.template_id == template.id))
    question = result.scalars().first()

    run = await _make_run(db, template, status=AuditStatus.IN_PROGRESS)
    db.add(
        AuditResponse(
            run_id=run.id,
            question_id=question.id,
            response_value="fail",
            applicability="applicable",
        )
    )
    db.add(
        AuditFinding(
            run_id=run.id,
            question_id=question.id,
            title="Brakes not functional",
            description="Observed defective brakes",
            severity="high",
            status=FindingStatus.OPEN,
            tenant_id=TENANT_ID,
            reference_number=generate_test_reference("FND"),
        )
    )
    await db.commit()

    service = AuditAnalyticsService(db)
    queue = await service.get_critical_queue(TENANT_ID)

    assert len(queue) == 1
    assert queue[0].reason == "failed_open_finding"
    assert queue[0].finding_status == "open"


@pytest.mark.asyncio
async def test_export_runs_csv_includes_dimensions_and_applicability(db: AsyncSession):
    from sqlalchemy import select

    template = await _seed_template_with_essential_question(db)
    result = await db.execute(select(AuditQuestion).where(AuditQuestion.template_id == template.id))
    question = result.scalars().first()

    run = await _make_run(db, template, status=AuditStatus.COMPLETED)
    run.customer_code = "ACME-001"
    db.add(
        AuditResponse(
            run_id=run.id,
            question_id=question.id,
            response_value="pass",
            score=1.0,
            max_score=1.0,
            applicability="applicable",
        )
    )
    await db.commit()

    service = AuditAnalyticsService(db)
    csv_text = await service.export_runs_csv(TENANT_ID, days=365)

    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("run_id,reference_number,status")
    assert "ACME-001" in csv_text
    assert "essential" in csv_text
    assert "applicable" in csv_text


@pytest.mark.asyncio
async def test_complete_run_essential_fail_overrides_passing_score(db: AsyncSession):
    """End-to-end: a failed essential answer fails the run even though the
    weighted percentage score clears the template's passing threshold.
    """
    from sqlalchemy import select

    template = await _seed_template_with_essential_question(db)
    result = await db.execute(select(AuditQuestion).where(AuditQuestion.template_id == template.id))
    question = result.scalars().first()
    # Second, non-essential question that scores full marks so the overall
    # percentage clears the 70% passing_score threshold despite the essential fail.
    bonus_question = AuditQuestion(
        template_id=template.id,
        question_text="Housekeeping tidy?",
        question_type="pass_fail",
        weight=4.0,
        max_score=4.0,
        is_required=True,
        criticality="good_to_have",
    )
    db.add(bonus_question)
    # Auto-finding/action/risk generation depends on tables outside this
    # isolated schema; disable it since we only assert the essential-fail gate.
    template.auto_create_findings = False
    await db.flush()
    await db.commit()

    run = await _make_run(db, template, status=AuditStatus.IN_PROGRESS)
    db.add(
        AuditResponse(run_id=run.id, question_id=question.id, response_value="fail", score=0.0, max_score=1.0)
    )
    db.add(
        AuditResponse(
            run_id=run.id, question_id=bonus_question.id, response_value="pass", score=4.0, max_score=4.0
        )
    )
    await db.commit()

    service = AuditService(db)
    completed = await service.complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)

    assert completed.score_percentage == 80.0  # 4/5 = 80%, clears passing_score=70
    assert completed.passed is False  # essential fail forces the run to fail
