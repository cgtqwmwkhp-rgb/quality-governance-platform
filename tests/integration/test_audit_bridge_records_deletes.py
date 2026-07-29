"""Deletes must leave an audit row — and only the row they can honestly claim.

PX-155 / C-30. Every one of these paths built an ``AuditEvent`` and threw it
away, because ``record_audit_event`` could not persist without a tenant_id and
44 of 71 call sites did not pass one. ``audit_log_entries`` in production held
39 rows in total, spanning update/create/portal_submit, with no delete or purge
among them at all.

The last test here is the boundary: it asserts what the trail does *not* cover,
so the coverage claim in the PR cannot quietly widen later.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.audit_log import AuditLogEntry
from src.domain.models.near_miss import NearMiss
from src.domain.services.audit_service import AuditService
from src.infrastructure.middleware.tenant_context import apply_tenant_guc

SEEDED_TENANT_ID = 1  # admin_client's JWT is user 1 / tenant 1


async def _entries(session, *, tenant_id: int, entity_type: str, action: str) -> list[AuditLogEntry]:
    await apply_tenant_guc(session, tenant_id)
    result = await session.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.tenant_id == tenant_id,
            AuditLogEntry.entity_type == entity_type,
            AuditLogEntry.action == action,
        )
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_deleting_a_near_miss_persists_an_audit_row(
    admin_client: AsyncClient,
    near_miss_factory,
    test_session,
) -> None:
    near_miss = await near_miss_factory()
    near_miss_id = near_miss["id"]

    response = await admin_client.delete(f"/api/v1/near-misses/{near_miss_id}")
    assert response.status_code in (200, 204), response.text

    rows = await _entries(test_session, tenant_id=SEEDED_TENANT_ID, entity_type="near_miss", action="delete")
    matching = [row for row in rows if row.entity_id == str(near_miss_id)]
    assert matching, "the near miss was deleted with no audit row written"
    entry = matching[0]
    assert entry.entry_hash, "an audit row outside the hash chain is not evidence"
    assert entry.entry_metadata["event_type"] == "near_miss.deleted"
    assert entry.user_id == 1


@pytest.mark.asyncio
async def test_deleting_a_running_sheet_entry_persists_an_audit_row(
    admin_client: AsyncClient,
    near_miss_factory,
    test_session,
) -> None:
    """The entry's own tenant_id column is nullable; the parent case supplies it."""
    near_miss = await near_miss_factory()
    near_miss_id = near_miss["id"]

    created = await admin_client.post(
        f"/api/v1/near-misses/{near_miss_id}/running-sheet",
        json={"content": "Site supervisor briefed", "entry_type": "note"},
    )
    assert created.status_code in (200, 201), created.text

    deleted = await admin_client.delete(f"/api/v1/near-misses/{near_miss_id}/running-sheet/{created.json()['id']}")
    assert deleted.status_code in (200, 204), deleted.text

    rows = await _entries(test_session, tenant_id=SEEDED_TENANT_ID, entity_type="near_miss", action="delete")
    events = {row.entry_metadata["event_type"] for row in rows}
    assert "near_miss.runner_sheet_entry.deleted" in events


@pytest.mark.asyncio
async def test_permanently_deleting_a_template_persists_an_audit_row(
    test_session,
    test_tenant,
    test_user,
) -> None:
    """The most destructive operation in the product, previously unrecorded."""
    service = AuditService(test_session)
    template = await service.create_template(
        {"name": "Depot weekly walkaround", "audit_type": "internal"},
        standard_ids=None,
        user_id=test_user.id,
        tenant_id=test_tenant.id,
    )
    template_id = template.id
    await service.archive_template(template_id, tenant_id=test_tenant.id, actor_user_id=test_user.id)
    await service.permanently_delete_template(
        template_id,
        tenant_id=test_tenant.id,
        actor_user_id=test_user.id,
    )
    await test_session.commit()

    rows = await _entries(
        test_session,
        tenant_id=test_tenant.id,
        entity_type="audit_template",
        action="permanent_delete",
    )
    assert [row.entity_id for row in rows] == [str(template_id)]
    assert rows[0].entry_metadata["event_type"] == "audit_template.permanently_deleted"


@pytest.mark.asyncio
async def test_purging_expired_templates_persists_an_audit_row(
    test_session,
    test_tenant,
    test_user,
) -> None:
    service = AuditService(test_session)
    template = await service.create_template(
        {"name": "Superseded checklist", "audit_type": "internal"},
        standard_ids=None,
        user_id=test_user.id,
        tenant_id=test_tenant.id,
    )
    await service.archive_template(template.id, tenant_id=test_tenant.id, actor_user_id=test_user.id)
    # Backdate past the 30-day recovery window the purge enforces.
    template.archived_at = datetime.now(timezone.utc) - timedelta(days=45)
    await test_session.flush()

    purged_count, purged_names = await service.purge_expired_templates(test_tenant.id, test_user.id)
    await test_session.commit()
    assert purged_count >= 1
    assert "Superseded checklist" in purged_names

    rows = await _entries(
        test_session,
        tenant_id=test_tenant.id,
        entity_type="audit_template",
        action="purge",
    )
    assert rows, "a bulk purge left no audit row"
    # The bridge files the payload under old_values only for the literal action
    # "delete", so "purge" and "permanent_delete" land in new_values. Asserted as
    # it behaves rather than as it reads.
    assert "Superseded checklist" in rows[0].new_values["purged_templates"]


@pytest.mark.asyncio
async def test_the_trail_records_the_case_delete_but_not_its_cascaded_children(
    admin_client: AsyncClient,
    near_miss_factory,
    test_session,
) -> None:
    """The honest limit of this change, asserted so it cannot be overstated.

    ``near_miss_running_sheet_entries.near_miss_id`` declares
    ``ondelete="CASCADE"`` and no relationship is mapped from ``NearMiss``, so
    PostgreSQL removes the entries itself and no Python event fires for them.
    The audit trail therefore says the case was deleted and says nothing about
    the entries that went with it.

    This asserts the audit rows, not the child rows: whether the children are
    actually gone depends on the engine (SQLite does not enforce foreign keys
    unless asked), while the audit gap is the same on both.
    """
    near_miss = await near_miss_factory()
    near_miss_id = near_miss["id"]
    entry = await admin_client.post(
        f"/api/v1/near-misses/{near_miss_id}/running-sheet",
        json={"content": "Entry that will vanish with the case", "entry_type": "note"},
    )
    assert entry.status_code in (200, 201), entry.text
    entry_id = entry.json()["id"]

    response = await admin_client.delete(f"/api/v1/near-misses/{near_miss_id}")
    assert response.status_code in (200, 204), response.text

    await apply_tenant_guc(test_session, SEEDED_TENANT_ID)
    case_gone = await test_session.execute(select(NearMiss).where(NearMiss.id == near_miss_id))
    assert case_gone.scalar_one_or_none() is None

    rows = await _entries(test_session, tenant_id=SEEDED_TENANT_ID, entity_type="near_miss", action="delete")
    events = [row.entry_metadata["event_type"] for row in rows if row.entity_id == str(near_miss_id)]
    assert "near_miss.deleted" in events

    entry_events = [
        row
        for row in rows
        if row.entry_metadata["event_type"] == "near_miss.runner_sheet_entry.deleted"
        and ((row.old_values or {}) | (row.new_values or {})).get("entry_id") == entry_id
    ]
    assert not entry_events, (
        "a running-sheet entry removed by the database cascade now has an audit "
        "row. If that is deliberate, update the coverage statement and "
        "tests/unit/test_delete_cascade_audit_visibility.py — do not leave the "
        "two disagreeing."
    )
