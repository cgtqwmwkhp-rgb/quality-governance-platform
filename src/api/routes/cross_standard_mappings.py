"""Cross-standard ISO mapping management API."""

import logging

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.utils.entity import get_or_404
from src.api.utils.update import apply_updates

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


class MappingCreate(BaseModel):
    primary_standard: str
    primary_clause: str
    mapped_standard: str
    mapped_clause: str
    mapping_type: str = "equivalent"
    mapping_strength: int = Field(5, ge=1, le=10)
    mapping_notes: str | None = None
    annex_sl_element: str | None = None


class MappingUpdate(BaseModel):
    mapping_type: str | None = None
    mapping_strength: int | None = Field(None, ge=1, le=10)
    mapping_notes: str | None = None
    annex_sl_element: str | None = None


@router.get("")
async def list_mappings(
    db: DbSession,
    current_user: CurrentUser,
    source_standard: str | None = Query(
        None, description="Filter by source/primary standard"
    ),
    target_standard: str | None = Query(
        None, description="Filter by target/mapped standard"
    ),
    clause: str | None = Query(
        None, description="Filter by clause number (matches source or target)"
    ),
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
    mapped = await db.execute(select(CrossStandardMapping.mapped_standard).distinct())
    all_standards = sorted(
        {s for (s,) in primaries.all()} | {s for (s,) in mapped.all()}
    )
    return {"standards": all_standards}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_mapping(
    data: MappingCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new cross-standard mapping."""
    from src.domain.models.ims_unification import CrossStandardMapping

    mapping = CrossStandardMapping(**data.model_dump())
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    return MappingResponse.model_validate(mapping)


@router.get("/{mapping_id}", response_model=MappingResponse)
async def get_mapping(
    mapping_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Retrieve a single cross-standard mapping by ID."""
    from src.domain.models.ims_unification import CrossStandardMapping

    return await get_or_404(db, CrossStandardMapping, mapping_id)


@router.patch("/{mapping_id}", response_model=MappingResponse)
async def update_mapping(
    mapping_id: int,
    data: MappingUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Partially update a cross-standard mapping."""
    from src.domain.models.ims_unification import CrossStandardMapping

    mapping = await get_or_404(db, CrossStandardMapping, mapping_id)
    apply_updates(mapping, data)
    await db.commit()
    await db.refresh(mapping)
    return MappingResponse.model_validate(mapping)


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mapping(
    mapping_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
):
    """Delete a cross-standard mapping (admin only)."""
    from src.domain.models.ims_unification import CrossStandardMapping

    mapping = await get_or_404(db, CrossStandardMapping, mapping_id)
    await db.delete(mapping)
    await db.commit()
