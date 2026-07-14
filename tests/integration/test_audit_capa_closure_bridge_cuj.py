"""Integration CUJ: audit finding CAPA verification→closed bridges finding status."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditFinding, AuditRun, AuditStatus, AuditTemplate, FindingStatus
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.notification import Notification
from src.infrastructure.database import engine
from tests.conftest import generate_test_reference

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="Audit CAPA bridge CUJ uses PostgreSQL-backed integration fixtures",
)


async def _seed_finding_with_capa(session: AsyncSession) -> tuple[AuditRun, AuditFinding, CAPAAction]:
    template = AuditTemplate(
        name="Closure bridge inspection",
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
        title="Closure bridge run",
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
        title="Missing edge protection",
        description="Scaffold missing toe boards",
        severity="high",
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
        title="Install toe boards",
        description="Corrective action for edge protection",
        capa_type=CAPAType.CORRECTIVE,
        status=CAPAStatus.IN_PROGRESS,
        priority=CAPAPriority.HIGH,
        source_type=CAPASource.AUDIT_FINDING,
        source_id=finding.id,
        created_by_id=1,
        assigned_to_id=1,
    )
    session.add(capa)
    await session.commit()
    await session.refresh(run)
    await session.refresh(finding)
    await session.refresh(capa)
    return run, finding, capa


async def test_capa_transition_bridges_finding_and_golden_thread(
    client,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    run, finding, capa = await _seed_finding_with_capa(test_session)
    finding_id = finding.id
    capa_id = capa.id
    run_id = run.id

    verify = await client.post(
        f"/api/v1/capa/{capa_id}/transition",
        headers=auth_headers,
        json={"status": "verification", "comment": "Work complete — awaiting verify"},
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["status"] == "verification"

    test_session.expire_all()
    finding_row = await test_session.get(AuditFinding, finding_id)
    assert finding_row is not None
    assert finding_row.status == FindingStatus.PENDING_VERIFICATION

    close = await client.post(
        f"/api/v1/capa/{capa_id}/transition",
        headers=auth_headers,
        json={"status": "closed", "comment": "Verified effective"},
    )
    assert close.status_code == 200, close.text
    assert close.json()["status"] == "closed"

    test_session.expire_all()
    finding_row = await test_session.get(AuditFinding, finding_id)
    assert finding_row is not None
    assert finding_row.status == FindingStatus.CLOSED

    # Idempotent re-close via unified actions path
    again = await client.patch(
        f"/api/v1/actions/{capa_id}?source_type=audit_finding",
        headers=auth_headers,
        json={"status": "closed"},
    )
    assert again.status_code == 200, again.text

    test_session.expire_all()
    finding_row = await test_session.get(AuditFinding, finding_id)
    assert finding_row is not None
    assert finding_row.status == FindingStatus.CLOSED

    thread = await client.get(
        f"/api/v1/audits/findings/{finding_id}/golden-thread",
        headers=auth_headers,
    )
    assert thread.status_code == 200, thread.text
    body = thread.json()
    assert body["finding"]["id"] == finding_id
    assert body["finding"]["run_id"] == run_id
    assert body["chain_status"] == "closed"
    assert body["capas"][0]["id"] == capa_id
    assert body["capas"][0]["status"] == "closed"
    assert any(e["event"] == "audit_finding.capa_closed" for e in body["events"])

    notif_result = await test_session.execute(
        select(Notification).where(
            Notification.user_id == 1,
            Notification.entity_type == "audit_finding",
            Notification.entity_id == str(finding_id),
        )
    )
    notifications = list(notif_result.scalars().all())
    assert len(notifications) >= 1
