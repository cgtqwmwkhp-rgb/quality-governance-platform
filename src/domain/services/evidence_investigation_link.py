"""Attach late source-record evidence to an already-open investigation.

create_from_record links assets that exist at open time. A photo uploaded to the
incident afterwards never received linked_investigation_id. Resolve the open
investigation from (assigned_entity_type, assigned_entity_id) and set the link
before commit. Investigation-native uploads are left alone — they already live
on source_module=investigation.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.evidence_asset import EvidenceSourceModule
from src.domain.models.investigation import AssignedEntityType, InvestigationRun

# Evidence modules use "incident"; investigations use "reporting_incident".
_SOURCE_MODULE_TO_ENTITY: dict[str, AssignedEntityType] = {
    EvidenceSourceModule.INCIDENT.value: AssignedEntityType.REPORTING_INCIDENT,
    EvidenceSourceModule.NEAR_MISS.value: AssignedEntityType.NEAR_MISS,
    EvidenceSourceModule.ROAD_TRAFFIC_COLLISION.value: AssignedEntityType.ROAD_TRAFFIC_COLLISION,
    EvidenceSourceModule.COMPLAINT.value: AssignedEntityType.COMPLAINT,
}


def assigned_entity_type_for_evidence_module(source_module: str | EvidenceSourceModule) -> Optional[AssignedEntityType]:
    """Map an evidence source_module to InvestigationRun.assigned_entity_type, or None."""
    key = source_module.value if isinstance(source_module, EvidenceSourceModule) else str(source_module or "")
    return _SOURCE_MODULE_TO_ENTITY.get(key)


async def resolve_linked_investigation_id(
    db: AsyncSession,
    *,
    source_module: str | EvidenceSourceModule,
    source_id: int | str,
    tenant_id: int | None,
) -> Optional[int]:
    """Return the investigation id for this source record, if one exists in-tenant.

    Source ids are per-tenant sequences. With no tenant we refuse to guess rather than
    attach another tenant's investigation.
    """
    if tenant_id is None:
        return None
    entity_type = assigned_entity_type_for_evidence_module(source_module)
    if entity_type is None:
        return None
    try:
        entity_id = int(source_id)
    except (TypeError, ValueError):
        return None

    query = select(InvestigationRun.id).where(
        InvestigationRun.tenant_id == tenant_id,
        InvestigationRun.assigned_entity_type == entity_type,
        InvestigationRun.assigned_entity_id == entity_id,
    )
    result = await db.execute(query)
    return result.scalars().first()
