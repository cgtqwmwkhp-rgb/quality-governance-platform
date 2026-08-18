"""PX-426: second POST /actions for the same audit finding is get-or-create.

``uq_capa_actions_tenant_audit_finding_source`` forbids a second row. The
operator shortcut used to map that unique hit to a reference-number 409.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditFinding, AuditRun, AuditStatus, AuditTemplate, FindingStatus
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.infrastructure.database import engine
from tests.conftest import generate_test_reference

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="partial unique index uq_capa_actions_tenant_audit_finding_source is Postgres",
)


async def _seed_open_finding_capa(session: AsyncSession) -> tuple[int, int, str]:
    template = AuditTemplate(
        name="PX-426 get-or-create inspection",
        category="Safety",
        audit_type="inspection",
        auto_create_findings=True,
        is_published=True,
        tenant_id=1,
        created_by_id=1,
        reference_number=generate_test_reference("TPL"),
    )
    session.add(template)
    await session.flush()

    run = AuditRun(
        template_id=template.id,
        title="PX-426 get-or-create run",
        location="Yard",
        status=AuditStatus.COMPLETED,
        tenant_id=1,
        assigned_to_id=1,
        created_by_id=1,
        reference_number=generate_test_reference("AUD"),
    )
    session.add(run)
    await session.flush()

    finding = AuditFinding(
        run_id=run.id,
        title="PX-426 already has a CAPA",
        description="W0 LIVE-02 shortcut",
        severity="medium",
        finding_type="nonconformity",
        status=FindingStatus.OPEN,
        corrective_action_required=True,
        tenant_id=1,
        created_by_id=1,
        reference_number=generate_test_reference("FND"),
    )
    session.add(finding)
    await session.flush()

    capa = CAPAAction(
        tenant_id=1,
        reference_number=generate_test_reference("CAPA"),
        title="PX-426 existing CAPA",
        description="Auto-created; unique index owns this finding",
        capa_type=CAPAType.CORRECTIVE,
        status=CAPAStatus.OPEN,
        priority=CAPAPriority.MEDIUM,
        source_type=CAPASource.AUDIT_FINDING,
        source_id=finding.id,
        created_by_id=1,
        assigned_to_id=1,
    )
    session.add(capa)
    await session.commit()
    await session.refresh(finding)
    await session.refresh(capa)
    return finding.id, capa.id, capa.reference_number


@pytest.mark.asyncio
async def test_second_post_same_finding_returns_existing_capa(
    client,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    finding_id, capa_id, ref = await _seed_open_finding_capa(test_session)

    response = await client.post(
        "/api/v1/actions/",
        headers=auth_headers,
        json={
            "title": "CAPA: duplicate shortcut",
            "description": "Operator clicked Create & assign",
            "source_type": "audit_finding",
            "source_id": finding_id,
            "priority": "high",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] == capa_id
    assert body["reference_number"] == ref
    assert body["source_id"] == finding_id
    assert body["source_type"] == "audit_finding"
    assert body["assigned_to_email"]

    count = await test_session.scalar(
        select(func.count())
        .select_from(CAPAAction)
        .where(
            CAPAAction.tenant_id == 1,
            CAPAAction.source_type == CAPASource.AUDIT_FINDING,
            CAPAAction.source_id == finding_id,
        )
    )
    assert count == 1
