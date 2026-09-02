"""Answer-type matrix smoke tests for audit answer-integrity gate (PR-A backend)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditQuestion, AuditRun, AuditSection, AuditStatus, AuditTemplate, TemplateVersion
from src.domain.models.evidence_asset import EvidenceAsset, EvidenceAssetType, EvidenceSourceModule
from src.domain.services.audit_service import COMPLETE_EVIDENCE_NOT_RESOLVED
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
    template_id = template.id
    expected_version = template.version
    question_id = question.id

    publish = await client.post(
        f"/api/v1/audits/templates/{template_id}/publish",
        headers=auth_headers,
    )
    assert publish.status_code == 200, publish.text

    test_session.expire_all()
    versions = await test_session.execute(select(TemplateVersion).where(TemplateVersion.template_id == template_id))
    version = versions.scalar_one()
    assert version.version_number == expected_version
    assert any(q["id"] == question_id for q in version.snapshot_json["questions"])


async def test_photo_answer_requires_evidence_asset_ids_for_complete(
    client,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """A photo answer's only content is its evidence, so the ids have to be real.

    AUD-F4 resolves ``evidence_asset_ids`` against ``evidence_assets`` for the
    run before completion believes them, so this walks the whole gate: no answer,
    then an answer citing an id that was never issued, then the real upload.
    """
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

    invented = await client.post(
        f"/api/v1/audits/runs/{run.id}/responses",
        headers=auth_headers,
        json={"question_id": question.id, "response_json": {"evidence_asset_ids": [2_000_000_001]}},
    )
    assert invented.status_code == 201, invented.text

    refused = await client.post(f"/api/v1/audits/runs/{run.id}/complete", headers=auth_headers)
    assert refused.status_code == 400, refused.text
    error = refused.json().get("error", {})
    assert error.get("code") == COMPLETE_EVIDENCE_NOT_RESOLVED
    assert 2_000_000_001 in (error.get("details", {}).get("unresolved_evidence_asset_ids") or [])

    test_session.expire_all()
    stored_run = await test_session.get(AuditRun, run.id)
    assert stored_run is not None
    assert stored_run.status == AuditStatus.IN_PROGRESS

    asset = EvidenceAsset(
        tenant_id=1,
        storage_key=f"audits/{run.id}/{generate_test_reference('EV')}.jpg",
        content_type="image/jpeg",
        asset_type=EvidenceAssetType.PHOTO,
        source_module=EvidenceSourceModule.AUDIT,
        source_id=str(run.id),
        description=f"audit_question:{question.id}",
    )
    test_session.add(asset)
    await test_session.commit()
    await test_session.refresh(asset)

    answered = await client.put(
        f"/api/v1/audits/runs/{run.id}/responses/by-question/{question.id}",
        headers=auth_headers,
        json={"response_json": {"evidence_asset_ids": [asset.id]}},
    )
    assert answered.status_code in (200, 201), answered.text

    complete = await client.post(f"/api/v1/audits/runs/{run.id}/complete", headers=auth_headers)
    assert complete.status_code == 200, complete.text
