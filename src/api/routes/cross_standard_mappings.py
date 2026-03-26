"""Cross-standard ISO mapping management API."""

import logging

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.utils.entity import get_or_404
from src.api.utils.update import apply_updates
from src.domain.models.ims_unification import IMSRequirement
from src.domain.models.standard import Clause, Standard
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)

router = APIRouter()


class MappingResponse(BaseModel):
    id: int
    primary_clause_id: int | None = None
    primary_standard: str
    primary_clause: str
    mapped_clause_id: int | None = None
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


class MappingListResponse(BaseModel):
    items: list[MappingResponse]


class StandardsListResponse(BaseModel):
    standards: list[str]


def _normalize_standard(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _standard_filters(value: str):
    normalized = _normalize_standard(value)
    return or_(
        Standard.code.ilike(f"%{value}%"),
        Standard.name.ilike(f"%{value}%"),
        Standard.full_name.ilike(f"%{value}%"),
        Standard.code.ilike(f"%{normalized}%"),
    )


async def _resolve_canonical_clause(
    db: DbSession,
    *,
    standard_name: str,
    clause_number: str,
    tenant_id: int | None,
) -> tuple["Standard", "Clause"]:
    standard_result = await db.execute(
        select(Standard).where(
            Standard.is_active == True,  # noqa: E712
            or_(Standard.tenant_id == tenant_id, Standard.tenant_id.is_(None)),
            _standard_filters(standard_name),
        )
    )
    standard = standard_result.scalars().first()
    if standard is None:
        raise HTTPException(status_code=404, detail=f"Standard not found: {standard_name}")

    clause_result = await db.execute(
        select(Clause).where(
            Clause.standard_id == standard.id,
            Clause.clause_number == clause_number,
            Clause.is_active == True,  # noqa: E712
            or_(Clause.tenant_id == tenant_id, Clause.tenant_id.is_(None)),
        )
    )
    clause = clause_result.scalars().first()
    if clause is None:
        raise HTTPException(status_code=404, detail=f"Clause not found: {standard.name} {clause_number}")

    return standard, clause


async def _get_or_create_ims_requirement(
    db: DbSession,
    *,
    standard: "Standard",
    clause: "Clause",
    tenant_id: int | None,
) -> "IMSRequirement":
    requirement_result = await db.execute(
        select(IMSRequirement).where(
            IMSRequirement.standard == standard.name,
            IMSRequirement.clause_number == clause.clause_number,
            IMSRequirement.tenant_id == tenant_id,
        )
    )
    requirement = requirement_result.scalars().first()
    if requirement is not None:
        return requirement

    requirement = IMSRequirement(
        tenant_id=tenant_id,
        clause_number=clause.clause_number,
        clause_title=clause.title,
        clause_text=clause.description or clause.title,
        standard=standard.name,
        level=clause.level,
        parent_clause=None,
        keywords=[clause.title],
    )
    db.add(requirement)
    await db.flush()
    return requirement


@router.get("", response_model=list[MappingResponse])
async def list_mappings(
    db: DbSession,
    current_user: CurrentUser,
    source_standard: str | None = Query(None, description="Filter by source/primary standard"),
    target_standard: str | None = Query(None, description="Filter by target/mapped standard"),
    clause: str | None = Query(None, description="Filter by clause number (matches source or target)"),
) -> list[MappingResponse]:
    """List cross-standard mappings with optional filters."""
    from src.domain.models.ims_unification import CrossStandardMapping

    query = select(CrossStandardMapping).where(CrossStandardMapping.tenant_id == current_user.tenant_id)
    if source_standard:
        query = query.where(CrossStandardMapping.primary_standard == source_standard)
    if target_standard:
        query = query.where(CrossStandardMapping.mapped_standard == target_standard)
    if clause:
        query = query.where(
            (CrossStandardMapping.primary_clause == clause) | (CrossStandardMapping.mapped_clause == clause)
        )

    result = await db.execute(query)
    rows = result.scalars().all()
    track_metric("cross_standard_mappings.accessed")
    return [MappingResponse.model_validate(r) for r in rows]


@router.get("/standards", response_model=StandardsListResponse)
async def list_standards(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """List all available ISO standards in the mapping database."""
    from src.domain.models.standard import Standard

    standards_result = await db.execute(
        select(Standard.name)
        .where(
            Standard.is_active == True,  # noqa: E712
            or_(Standard.tenant_id == current_user.tenant_id, Standard.tenant_id.is_(None)),
        )
        .order_by(Standard.name.asc())
    )
    all_standards = [name for (name,) in standards_result.all()]
    return {"standards": all_standards}


@router.post("", response_model=MappingResponse, status_code=status.HTTP_201_CREATED)
async def create_mapping(
    data: MappingCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new cross-standard mapping."""
    from src.domain.models.ims_unification import CrossStandardMapping

    primary_standard, primary_clause = await _resolve_canonical_clause(
        db,
        standard_name=data.primary_standard,
        clause_number=data.primary_clause,
        tenant_id=current_user.tenant_id,
    )
    mapped_standard, mapped_clause = await _resolve_canonical_clause(
        db,
        standard_name=data.mapped_standard,
        clause_number=data.mapped_clause,
        tenant_id=current_user.tenant_id,
    )

    existing_result = await db.execute(
        select(CrossStandardMapping).where(
            CrossStandardMapping.tenant_id == current_user.tenant_id,
            CrossStandardMapping.primary_clause_id == primary_clause.id,
            CrossStandardMapping.mapped_clause_id == mapped_clause.id,
        )
    )
    existing = existing_result.scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Cross-standard mapping already exists")

    primary_requirement = await _get_or_create_ims_requirement(
        db,
        standard=primary_standard,
        clause=primary_clause,
        tenant_id=current_user.tenant_id,
    )
    mapped_requirement = await _get_or_create_ims_requirement(
        db,
        standard=mapped_standard,
        clause=mapped_clause,
        tenant_id=current_user.tenant_id,
    )

    mapping = CrossStandardMapping(
        tenant_id=current_user.tenant_id,
        primary_clause_id=primary_clause.id,
        primary_requirement_id=primary_requirement.id,
        primary_standard=primary_standard.name,
        primary_clause=primary_clause.clause_number,
        mapped_clause_id=mapped_clause.id,
        mapped_requirement_id=mapped_requirement.id,
        mapped_standard=mapped_standard.name,
        mapped_clause=mapped_clause.clause_number,
        mapping_type=data.mapping_type,
        mapping_strength=data.mapping_strength,
        mapping_notes=data.mapping_notes,
        annex_sl_element=data.annex_sl_element,
    )
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    track_metric("mappings.created", 1)
    return MappingResponse.model_validate(mapping)


@router.get("/{mapping_id}", response_model=MappingResponse)
async def get_mapping(
    mapping_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Retrieve a single cross-standard mapping by ID."""
    from src.domain.models.ims_unification import CrossStandardMapping

    return await get_or_404(db, CrossStandardMapping, mapping_id, tenant_id=current_user.tenant_id)


@router.patch("/{mapping_id}", response_model=MappingResponse)
async def update_mapping(
    mapping_id: int,
    data: MappingUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Partially update a cross-standard mapping."""
    from src.domain.models.ims_unification import CrossStandardMapping

    mapping = await get_or_404(db, CrossStandardMapping, mapping_id, tenant_id=current_user.tenant_id)
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

    mapping = await get_or_404(db, CrossStandardMapping, mapping_id, tenant_id=current_user.tenant_id)
    await db.delete(mapping)
    await db.commit()
