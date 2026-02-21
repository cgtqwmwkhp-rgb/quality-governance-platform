"""Cross-standard ISO mapping management API."""

import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession

logger = logging.getLogger(__name__)

router = APIRouter()


class MappingResponse(BaseModel):
    id: int
    primary_standard: str
    primary_clause: str
    mapped_standard: str
    mapped_clause: str
    mapping_type: str
    mapping_strength: int
    mapping_notes: str | None = None
    annex_sl_element: str | None = None

    class Config:
        from_attributes = True


@router.get("")
async def list_mappings(
    db: DbSession,
    current_user: CurrentUser,
    source_standard: str | None = Query(None, description="Filter by source/primary standard"),
    target_standard: str | None = Query(None, description="Filter by target/mapped standard"),
    clause: str | None = Query(None, description="Filter by clause number (matches source or target)"),
) -> list[MappingResponse]:
    """List cross-standard mappings with optional filters."""
    from src.domain.models.ims_unification import CrossStandardMapping

    query = select(CrossStandardMapping)
    if source_standard:
        query = query.where(CrossStandardMapping.primary_standard == source_standard)
    if target_standard:
        query = query.where(CrossStandardMapping.mapped_standard == target_standard)
    if clause:
        query = query.where(
            (CrossStandardMapping.primary_clause == clause)
            | (CrossStandardMapping.mapped_clause == clause)
        )

    result = await db.execute(query)
    rows = result.scalars().all()
    return [MappingResponse.model_validate(r) for r in rows]


@router.get("/standards")
async def list_standards(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all available ISO standards in the mapping database."""
    from src.domain.models.ims_unification import CrossStandardMapping

    primaries = await db.execute(
        select(CrossStandardMapping.primary_standard).distinct()
    )
    mapped = await db.execute(
        select(CrossStandardMapping.mapped_standard).distinct()
    )
    all_standards = sorted(
        {s for (s,) in primaries.all()} | {s for (s,) in mapped.all()}
    )
    return {"standards": all_standards}
