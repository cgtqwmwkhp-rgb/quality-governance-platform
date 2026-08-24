"""Print a persisted audit row end to end, as reviewable evidence for C-5 / PX-142b.

Not a substitute for the assertions in ``test_audit_entry_is_evidential`` — this
exists so the values can be read rather than inferred from a green tick.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.audit_log import AuditLogEntry
from src.infrastructure.middleware.tenant_context import apply_tenant_guc

pytestmark = pytest.mark.asyncio


async def test_dump_audit_entries_after_create_and_update(client: AsyncClient, auth_headers, test_session):
    headers = {
        **auth_headers,
        "X-Forwarded-For": "203.0.113.42",
        "User-Agent": "Mozilla/5.0 (QGP evidence dump)",
    }

    created = await client.post(
        "/api/v1/incidents/",
        json={
            "title": "Evidence dump incident",
            "description": "Show the values",
            "incident_type": "injury",
            "severity": "low",
            "status": "reported",
            "incident_date": datetime.now(timezone.utc).isoformat(),
            "location": "Lab",
            "department": "QA",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    incident_id = str(created.json()["id"])

    patched = await client.patch(
        f"/api/v1/incidents/{incident_id}",
        json={"location": "Workshop", "severity": "medium"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text

    await apply_tenant_guc(test_session, 1)
    test_session.expire_all()
    rows = (
        (
            await test_session.execute(
                select(AuditLogEntry)
                .where(
                    AuditLogEntry.tenant_id == 1,
                    AuditLogEntry.entity_type == "incident",
                    AuditLogEntry.entity_id == incident_id,
                )
                .order_by(AuditLogEntry.sequence)
            )
        )
        .scalars()
        .all()
    )

    print("\n" + "=" * 78)
    print("PERSISTED audit_log_entries (read back from the database)")
    print("=" * 78)
    for r in rows:
        print(f"  sequence       : {r.sequence}")
        print(f"  action         : {r.action}")
        print(f"  entity         : {r.entity_type}:{r.entity_id}")
        print(f"  entity_name    : {r.entity_name!r}")
        print(f"  changed_fields : {r.changed_fields!r}")
        print(f"  ip_address     : {r.ip_address!r}")
        print(f"  user_agent     : {r.user_agent!r}")
        print(f"  user_name      : {r.user_name!r}")
        print(f"  user_email     : {r.user_email!r}")
        print("-" * 78)

    assert rows, "no audit rows written"
