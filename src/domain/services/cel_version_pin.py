"""CEL document version pin helpers (ADR-0021 P0).

Evidence links for ``entity_type=document`` should record which library
``DocumentVersion`` tip they were created/confirmed against. Nullable is OK —
callers pin best-effort when a tip is known.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.services.document_version_service import document_version_service


def parse_document_entity_id(entity_id: str | int | None) -> Optional[int]:
    if entity_id is None:
        return None
    try:
        return int(entity_id)
    except (TypeError, ValueError):
        return None


async def resolve_document_tip_version_id(
    db: AsyncSession,
    *,
    document_id: int,
    tenant_id: int,
) -> Optional[int]:
    tip = await document_version_service.resolve_tip_library_version(
        db,
        document_id=document_id,
        tenant_id=tenant_id,
    )
    return tip.id if tip is not None else None


async def pin_evidence_link_document_version(
    db: AsyncSession,
    link: Any,
    *,
    tenant_id: int,
    force: bool = False,
) -> Optional[int]:
    """Set ``link.document_version_id`` from the library tip when applicable.

    Returns the pinned version id (existing or newly resolved), else None.
    """
    if getattr(link, "entity_type", None) != "document":
        return None
    existing = getattr(link, "document_version_id", None)
    if existing is not None and not force:
        return int(existing)

    document_id = parse_document_entity_id(getattr(link, "entity_id", None))
    if document_id is None:
        return None

    tip_id = await resolve_document_tip_version_id(
        db,
        document_id=document_id,
        tenant_id=tenant_id,
    )
    if tip_id is not None:
        link.document_version_id = tip_id
    return tip_id
