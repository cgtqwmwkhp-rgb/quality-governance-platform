"""Answer-type matrix smoke tests for audit answer-integrity gate (PR-A backend)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import (
    AuditQuestion,
    AuditRun,
    AuditSection,
    AuditStatus,
    AuditTemplate,
    TemplateVersion,
)
from src.infrastructure.database import engine
from tests.conftest import generate_test_reference

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="Inspection risk materialization uses PostgreSQL JSONB containment",
)


async def _seed_photo_question(session: AsyncSession) -> tuple[AuditTemplate, AuditQuestion]:
    template = AuditTemplate(
        name="Answer integrity photo gate",
        category="Safety",
        audit_type="inspection",
        auto_create_findings=False,
        is_published=False,
        is_active=True,
        tenant_id=1,
        created_by_id=1,
        version=1,
        reference_number=generate_test_reference("TPL"),
    )
    session.add(template)
    await session.flush()

    section = AuditSection(template_id=template.id, title="Evidence", sort_order=1, weight=1.0)
    session.add(section)
    await session.flush()

    question = AuditQuestion(
        template_id=template.id,
        section_id=section.id,
        question_text="Attach site photo",
        question_type="photo",
        is_required=True,
        sort_order=1,
        weight=1.0,
    )
    session.add(question)
    await session.flush()
    await session.commit()
    await session.refresh(template)
    await session.refresh(question)
    return template, question


async def test_publish_writes_template_version_snapshot(
    client,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    template, question = await _seed_photo_question(test_session)

    publish = await client.post(
        f"/api/v1/audits/templates/{template.id}/publish",
        headers=auth_headers,
    )
    assert publish.status_code == 200, publish.text

    test_session.expire_all()
    versions = await test_session.execute(
        select(TemplateVersion).where(TemplateVersion.template_id == template.id)
    )
    version = versions.scalar_one()
    assert version.version_number == template.version
    assert any(q["id"] == question.id for q in version.snapshot_json["questions"])


async def test_photo_answer_requires_evidence_asset_ids_for_complete(
    client,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    template, question = await _seed_photo_question(test_session)
    publish = await client.post(
        f"/api/v1/audits/templates/{template.id}/publish",
        headers=auth_headers,
    )
    assert publish.status_code == 200, publish.text

    run = AuditRun(
        template_id=template.id,
        title="Photo gate run",
        status=AuditStatus.IN_PROGRESS,
        tenant_id=1,
        assigned_to_id=1,
        created_by_id=1,
        reference_number=generate_test_reference("AUD"),
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)

    blocked = await client.post(f"/api/v1/audits/runs/{run.id}/complete", headers=auth_headers)
    assert blocked.status_code == 400, blocked.text
    details = blocked.json().get("error", {}).get("details") or {}
    assert question.id in (details.get("missing_question_ids") or [])

    answered = await client.post(
        f"/api/v1/audits/runs/{run.id}/responses",
        headers=auth_headers,
        json={"question_id": question.id, "response_json": {"evidence_asset_ids": [101]}},
    )
    assert answered.status_code == 201, answered.text

    complete = await client.post(f"/api/v1/audits/runs/{run.id}/complete", headers=auth_headers)
    assert complete.status_code == 200, complete.text
