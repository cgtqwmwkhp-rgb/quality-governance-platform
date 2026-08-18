"""PX-424: PATCH CAPA close via unified Actions must not 500 on Postgres.

The dedicated ``POST /capa/{id}/transition`` path already writes naive UTC.
The UAT close button uses ``PATCH /actions/{id}?source_type=audit_finding``
with a terminal status while ``completed_at`` is still null — that is the
path that assigned an aware datetime and asyncpg rejected.

SQLite accepts the same write, so these skip off Postgres.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditFinding, AuditRun, AuditStatus, AuditTemplate, FindingStatus
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.infrastructure.database import engine
from tests.conftest import generate_test_reference

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="aware-vs-naive CAPA DateTime mismatch is only rejected by asyncpg",
)


async def _seed_open_finding_capa(session: AsyncSession) -> tuple[int, int]:
    template = AuditTemplate(
        name="PX-424 close inspection",
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
        title="PX-424 close run",
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
        title="PX-424 floors unsafe",
        description="W0 LIVE-02 close path",
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
        title="PX-424 close CAPA",
        description="Must close via PATCH /actions without 500",
        capa_type=CAPAType.CORRECTIVE,
        status=CAPAStatus.IN_PROGRESS,
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
    return finding.id, capa.id


@pytest.mark.asyncio
async def test_patch_completed_from_in_progress_does_not_500(
    client,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    finding_id, capa_id = await _seed_open_finding_capa(test_session)

    close = await client.patch(
        f"/api/v1/actions/{capa_id}?source_type=audit_finding",
        headers=auth_headers,
        json={"status": "completed"},
    )
    assert close.status_code == 200, close.text
    body = close.json()
    assert body["display_status"] in {"completed", "closed"}
    assert body["id"] == capa_id

    test_session.expire_all()
    capa = await test_session.get(CAPAAction, capa_id)
    assert capa is not None
    assert capa.status == CAPAStatus.CLOSED
    assert capa.completed_at is not None
    assert capa.completed_at.tzinfo is None

    finding = await test_session.get(AuditFinding, finding_id)
    assert finding is not None
    assert finding.status == FindingStatus.CLOSED


@pytest.mark.asyncio
async def test_patch_zulu_due_date_does_not_500(
    client,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    _finding_id, capa_id = await _seed_open_finding_capa(test_session)

    response = await client.patch(
        f"/api/v1/actions/{capa_id}?source_type=audit_finding",
        headers=auth_headers,
        json={"due_date": "2026-09-01T00:00:00Z"},
    )
    assert response.status_code == 200, response.text

    test_session.expire_all()
    capa = await test_session.get(CAPAAction, capa_id)
    assert capa is not None
    assert capa.due_date is not None
    assert capa.due_date.tzinfo is None
    assert capa.status == CAPAStatus.IN_PROGRESS
