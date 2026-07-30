"""Integration spec: unified Actions ownership counts both physical columns.

Seeds one CAPA row owned via ``assigned_to_id`` and one incident action owned via
``owner_id``, then asserts ``GET /api/v1/actions/`` reports both as owned under
the single response field ``owner_id``. That is the register truth for
``w3-owner-count`` — not a raw SQL probe against one column name.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.incident import (
    ActionStatus,
    Incident,
    IncidentAction,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
)
from src.infrastructure.database import async_session_maker

TENANT = 1
LIST = "/api/v1/actions/"


def _aware(days_from_now: float) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days_from_now)


async def _list_by_source(client: AsyncClient, source_type: str) -> dict[str, dict]:
    response = await client.get(LIST, params={"source_type": source_type, "page_size": 100})
    assert response.status_code == 200, response.text
    body = response.json()
    items = list(body.get("items") or [])
    return {item["reference_number"]: item for item in items if item.get("reference_number")}


async def _seed_owned_and_unowned(*, tag: str) -> tuple[str, str, str, str]:
    """Return (owned_capa_ref, unowned_capa_ref, owned_iact_ref, unowned_iact_ref)."""
    owned_capa = f"CAPA-OWN-{tag}-001"
    unowned_capa = f"CAPA-OWN-{tag}-000"
    owned_iact = f"IACT-OWN-{tag}-001"
    unowned_iact = f"IACT-OWN-{tag}-000"
    async with async_session_maker() as session:
        session.add(
            CAPAAction(
                tenant_id=TENANT,
                reference_number=owned_capa,
                title=f"Owned CAPA {tag}",
                description="Seeded for ownership count reconciliation.",
                capa_type=CAPAType.CORRECTIVE,
                status=CAPAStatus.OPEN,
                priority=CAPAPriority.MEDIUM,
                source_type=CAPASource.MANAGEMENT_REVIEW,
                source_id=None,
                created_by_id=1,
                assigned_to_id=1,
            )
        )
        session.add(
            CAPAAction(
                tenant_id=TENANT,
                reference_number=unowned_capa,
                title=f"Unowned CAPA {tag}",
                description="Seeded for ownership count reconciliation.",
                capa_type=CAPAType.CORRECTIVE,
                status=CAPAStatus.OPEN,
                priority=CAPAPriority.MEDIUM,
                source_type=CAPASource.MANAGEMENT_REVIEW,
                source_id=None,
                created_by_id=1,
                assigned_to_id=None,
            )
        )
        incident = Incident(
            tenant_id=TENANT,
            reference_number=f"INC-OWN-{tag}",
            title=f"Ownership count incident {tag}",
            description="Seeded for ownership count reconciliation.",
            incident_type=IncidentType.OTHER,
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.PENDING_ACTIONS,
            incident_date=_aware(-10),
            reported_date=_aware(-10),
            created_by_id=1,
        )
        session.add(incident)
        await session.flush()
        session.add(
            IncidentAction(
                tenant_id=TENANT,
                incident_id=incident.id,
                reference_number=owned_iact,
                title=f"Owned incident action {tag}",
                description="Seeded for ownership count reconciliation.",
                status=ActionStatus.OPEN,
                due_date=_aware(7),
                owner_id=1,
            )
        )
        session.add(
            IncidentAction(
                tenant_id=TENANT,
                incident_id=incident.id,
                reference_number=unowned_iact,
                title=f"Unowned incident action {tag}",
                description="Seeded for ownership count reconciliation.",
                status=ActionStatus.OPEN,
                due_date=_aware(7),
                owner_id=None,
            )
        )
        await session.commit()
    return owned_capa, unowned_capa, owned_iact, unowned_iact


@pytest.mark.asyncio
async def test_unified_list_reports_capa_assigned_to_id_as_owner_id(admin_client: AsyncClient) -> None:
    tag = uuid.uuid4().hex[:6]
    owned_capa, unowned_capa, owned_iact, unowned_iact = await _seed_owned_and_unowned(tag=tag)

    capas = await _list_by_source(admin_client, "capa")
    incidents = await _list_by_source(admin_client, "incident")

    assert owned_capa in capas, f"seeded owned CAPA missing; sample={sorted(capas)[:12]}"
    assert unowned_capa in capas
    assert owned_iact in incidents
    assert unowned_iact in incidents

    assert capas[owned_capa]["owner_id"] == 1, (
        "CAPA assigned_to_id must surface as response.owner_id on GET /actions/ — "
        "this is the register truth for w3-owner-count."
    )
    assert capas[unowned_capa]["owner_id"] is None
    assert incidents[owned_iact]["owner_id"] == 1
    assert incidents[unowned_iact]["owner_id"] is None


@pytest.mark.asyncio
async def test_both_physical_columns_contribute_one_owned_register_row_each(
    admin_client: AsyncClient,
) -> None:
    """One owned CAPA + one owned incident action → two owned unified rows."""
    tag = uuid.uuid4().hex[:6]
    owned_capa, unowned_capa, owned_iact, unowned_iact = await _seed_owned_and_unowned(tag=tag)

    capas = await _list_by_source(admin_client, "capa")
    incidents = await _list_by_source(admin_client, "incident")
    seeded = [
        capas[owned_capa],
        capas[unowned_capa],
        incidents[owned_iact],
        incidents[unowned_iact],
    ]
    owned = [row for row in seeded if row.get("owner_id") is not None]
    assert len(owned) == 2
    assert {row["reference_number"] for row in owned} == {owned_capa, owned_iact}
