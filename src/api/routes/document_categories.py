"""Governance Library taxonomy API (Wave W0).

Read-only category tree for any active user (matches access-policy.md:
"categories, tags, sites: Read: any active user; Write: admin only"), plus
an admin-only idempotent reseed action for re-applying
specs/governance-library/taxonomy.json after an edit.
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.domain.models.document_library import DocumentCategory, DocumentTag
from src.domain.models.user import User
from src.domain.services.document_category_service import CategorySeedResult, seed_document_categories

router = APIRouter()
logger = logging.getLogger(__name__)


class DocumentCategoryResponse(BaseModel):
    """A single taxonomy category (flat row)."""

    id: int
    taxonomy_id: str
    parent_id: Optional[int]
    level: int
    sort_order: int
    name: str
    slug: str
    ref_prefix: str
    description: Optional[str]
    default_access: Optional[str]
    suggested_owner_role: Optional[str]
    review_cycle: Optional[str]
    retention_rule: Optional[str]
    active: bool

    class Config:
        from_attributes = True


class DocumentCategoryTreeNode(DocumentCategoryResponse):
    """A level-1 section with its level-2 subcategories nested."""

    children: list[DocumentCategoryResponse] = []


class DocumentCategoryTreeResponse(BaseModel):
    """Full taxonomy tree."""

    sections: list[DocumentCategoryTreeNode]
    total_categories: int
    total_active: int


class DocumentTagResponse(BaseModel):
    """A document classification tag."""

    id: int
    slug: str
    label: str
    group: str
    active: bool

    class Config:
        from_attributes = True


class SeedResultResponse(BaseModel):
    """Outcome of an idempotent taxonomy reseed."""

    categories_created: int
    categories_updated: int
    tags_created: int
    tags_updated: int
    counters_created: int
    total_categories: int
    total_tags: int

    @classmethod
    def from_result(cls, result: CategorySeedResult) -> "SeedResultResponse":
        return cls(
            categories_created=result.categories_created,
            categories_updated=result.categories_updated,
            tags_created=result.tags_created,
            tags_updated=result.tags_updated,
            counters_created=result.counters_created,
            total_categories=result.total_categories,
            total_tags=result.total_tags,
        )


@router.get("", response_model=DocumentCategoryTreeResponse, include_in_schema=False)
@router.get("/", response_model=DocumentCategoryTreeResponse)
async def get_document_category_tree(
    db: DbSession,
    current_user: CurrentUser,
    include_inactive: bool = False,
) -> DocumentCategoryTreeResponse:
    """Return the Governance Library taxonomy as a 2-level section > subcategory tree.

    `include_inactive=false` (default) hides retired categories (e.g. 06.04
    O-Licence & Tachograph) from pickers while keeping them in the DB for
    provenance — matches the Wave W0 deactivation decision.
    """
    del current_user  # any active user may read (access-policy.md)
    query = select(DocumentCategory).order_by(DocumentCategory.level, DocumentCategory.sort_order)
    if not include_inactive:
        query = query.where(DocumentCategory.active.is_(True))

    result = await db.execute(query)
    categories = result.scalars().all()

    sections_by_id: dict[int, DocumentCategoryTreeNode] = {}
    children_by_parent: dict[int, list[DocumentCategoryResponse]] = {}

    for category in categories:
        # Validate via the flat response first so Pydantic never touches the
        # SQLAlchemy `children` relationship (lazy IO outside the async greenlet).
        flat = DocumentCategoryResponse.model_validate(category, from_attributes=True)
        if category.level == 1:
            sections_by_id[category.id] = DocumentCategoryTreeNode(**flat.model_dump(), children=[])
        else:
            if category.parent_id is not None:
                children_by_parent.setdefault(category.parent_id, []).append(flat)

    sections = list(sections_by_id.values())
    for section in sections:
        section.children = children_by_parent.get(section.id, [])

    total_result = await db.execute(select(DocumentCategory))
    all_categories = total_result.scalars().all()
    return DocumentCategoryTreeResponse(
        sections=sections,
        total_categories=len(all_categories),
        total_active=sum(1 for c in all_categories if c.active),
    )


@router.get("/tags", response_model=list[DocumentTagResponse])
async def list_document_tags(
    db: DbSession,
    current_user: CurrentUser,
    include_inactive: bool = False,
) -> list[DocumentTagResponse]:
    """List the controlled tag vocabulary (any active user may read)."""
    del current_user
    query = select(DocumentTag).order_by(DocumentTag.group, DocumentTag.label)
    if not include_inactive:
        query = query.where(DocumentTag.active.is_(True))
    result = await db.execute(query)
    return [DocumentTagResponse.model_validate(t, from_attributes=True) for t in result.scalars().all()]


class LibraryRbacCatalogResponse(BaseModel):
    """Wave W2 — facet bundles + restricted taxonomy → permission map."""

    facets: dict[str, list[str]]
    restricted_taxonomy_permissions: dict[str, str]


@router.get("/rbac-catalog", response_model=LibraryRbacCatalogResponse)
async def get_library_rbac_catalog(
    current_user: CurrentUser,
) -> LibraryRbacCatalogResponse:
    """Return staff/manager/admin facet bundles and restricted category gates."""
    del current_user
    from src.domain.services.document_library_rbac import RESTRICTED_TAXONOMY_PERMISSIONS, facet_permission_bundles

    return LibraryRbacCatalogResponse(
        facets=facet_permission_bundles(),
        restricted_taxonomy_permissions=dict(RESTRICTED_TAXONOMY_PERMISSIONS),
    )


@router.post("/reseed", response_model=SeedResultResponse)
async def reseed_document_categories(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
) -> SeedResultResponse:
    """Admin-only: idempotently re-apply specs/governance-library/taxonomy.json.

    Safe to call at any time — upserts by natural key, never duplicates,
    and always re-forces the Wave W0 deactivation list (06.04).
    """
    del current_user
    result = await seed_document_categories(db)
    await db.commit()
    logger.info(
        "Governance Library taxonomy reseeded: %s categories created, %s updated (total %s)",
        result.categories_created,
        result.categories_updated,
        result.total_categories,
    )
    return SeedResultResponse.from_result(result)
