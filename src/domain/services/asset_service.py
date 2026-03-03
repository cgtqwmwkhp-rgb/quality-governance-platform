"""Asset Registry domain service.

Provides business logic and data access for asset types, assets,
and template-asset-type linkages. All operations are tenant-scoped.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.exceptions import NotFoundError
from src.domain.models.asset import Asset, AssetCategory, AssetStatus, AssetType, TemplateAssetType
from src.domain.models.audit import AuditTemplate

# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PaginatedResult:
    items: list[Any]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# AssetService
# ---------------------------------------------------------------------------


class AssetService:
    """Domain service encapsulating asset registry business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_entity(
        self,
        model: type,
        entity_id: int,
        *,
        tenant_id: int | None = None,
    ) -> Any:
        """Fetch entity by PK, optionally scoped to *tenant_id*."""
        model_any: Any = model
        stmt = select(model).where(model_any.id == entity_id)
        if tenant_id is not None:
            stmt = stmt.where(
                or_(
                    model_any.tenant_id == tenant_id,
                    model_any.tenant_id.is_(None),
                )
            )
        result = await self.db.execute(stmt)
        entity = result.scalar_one_or_none()
        if entity is None:
            raise NotFoundError(f"{model.__name__} {entity_id} not found")
        return entity

    async def _paginate(self, query: Any, page: int, page_size: int) -> PaginatedResult:
        offset = (page - 1) * page_size
        count_q = select(func.count()).select_from(query.subquery())
        total: int = (await self.db.execute(count_q)).scalar_one()
        items = (await self.db.execute(query.offset(offset).limit(page_size))).scalars().all()
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        return PaginatedResult(
            items=list(items),
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    @staticmethod
    def _apply_dict(entity: object, data: dict[str, Any], *, exclude: set[str] | None = None) -> None:
        """Apply *data* values to a SQLAlchemy model instance."""
        exclude = exclude or set()
        for key, value in data.items():
            if key in exclude:
                continue
            if hasattr(entity, key):
                setattr(entity, key, value)
        if hasattr(entity, "updated_at"):
            entity.updated_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]

    # ==================================================================
    # Asset Type methods
    # ==================================================================

    async def list_asset_types(
        self,
        tenant_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> PaginatedResult:
        query = select(AssetType).where(
            or_(
                AssetType.tenant_id == tenant_id,
                AssetType.tenant_id.is_(None),
            )
        )
        if search:
            pattern = f"%{search}%"
            query = query.where(AssetType.name.ilike(pattern) | AssetType.description.ilike(pattern))
        if category:
            try:
                cat_enum = AssetCategory(category)
                query = query.where(AssetType.category == cat_enum)
            except ValueError:
                pass  # Invalid category, ignore filter
        if is_active is not None:
            query = query.where(AssetType.is_active == is_active)
        query = query.order_by(AssetType.category, AssetType.name)
        return await self._paginate(query, page, page_size)

    async def create_asset_type(
        self,
        data: dict[str, Any],
        *,
        user_id: int,
        tenant_id: int,
    ) -> AssetType:
        if "category" in data:
            data["category"] = AssetCategory(data["category"])
        asset_type = AssetType(
            **data,
            created_by_id=user_id,
            updated_by_id=user_id,
            tenant_id=tenant_id,
        )
        self.db.add(asset_type)
        await self.db.commit()
        await self.db.refresh(asset_type)
        return asset_type

    async def update_asset_type(
        self,
        asset_type_id: int,
        update_data: dict[str, Any],
        *,
        tenant_id: int,
        actor_user_id: int,
    ) -> AssetType:
        asset_type: AssetType = await self._get_entity(
            AssetType,
            asset_type_id,
            tenant_id=tenant_id,
        )
        if "category" in update_data:
            update_data["category"] = AssetCategory(update_data["category"])
        self._apply_dict(asset_type, update_data, exclude={"id", "tenant_id"})
        asset_type.updated_by_id = actor_user_id
        await self.db.commit()
        await self.db.refresh(asset_type)
        return asset_type

    async def delete_asset_type(
        self,
        asset_type_id: int,
        *,
        tenant_id: int,
    ) -> None:
        asset_type: AssetType = await self._get_entity(
            AssetType,
            asset_type_id,
            tenant_id=tenant_id,
        )
        await self.db.delete(asset_type)
        await self.db.commit()

    # ==================================================================
    # Asset methods
    # ==================================================================

    async def list_assets(
        self,
        tenant_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        asset_type_id: int | None = None,
        status: str | None = None,
        site: str | None = None,
    ) -> PaginatedResult:
        query = (
            select(Asset)
            .options(selectinload(Asset.asset_type))
            .where(
                or_(
                    Asset.tenant_id == tenant_id,
                    Asset.tenant_id.is_(None),
                )
            )
        )
        if search:
            pattern = f"%{search}%"
            query = query.where(
                Asset.name.ilike(pattern) | Asset.asset_number.ilike(pattern) | Asset.description.ilike(pattern)
            )
        if asset_type_id is not None:
            query = query.where(Asset.asset_type_id == asset_type_id)
        if status is not None:
            try:
                status_enum = AssetStatus(status)
                query = query.where(Asset.status == status_enum)
            except ValueError:
                pass
        if site is not None:
            query = query.where(Asset.site.ilike(f"%{site}%"))
        query = query.order_by(Asset.asset_number)
        return await self._paginate(query, page, page_size)

    async def create_asset(
        self,
        data: dict[str, Any],
        *,
        user_id: int,
        tenant_id: int,
    ) -> Asset:
        if "status" in data:
            data["status"] = AssetStatus(data["status"])
        metadata = data.pop("metadata_json", data.pop("metadata", None))
        if metadata is not None:
            data["metadata_json"] = metadata
        asset = Asset(
            **data,
            created_by_id=user_id,
            updated_by_id=user_id,
            tenant_id=tenant_id,
        )
        self.db.add(asset)
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def get_asset(
        self,
        asset_id: int,
        tenant_id: int,
    ) -> Asset:
        result = await self.db.execute(
            select(Asset)
            .options(selectinload(Asset.asset_type))
            .where(
                Asset.id == asset_id,
                or_(
                    Asset.tenant_id == tenant_id,
                    Asset.tenant_id.is_(None),
                ),
            )
        )
        asset = result.scalar_one_or_none()
        if not asset:
            raise NotFoundError(f"Asset {asset_id} not found")
        return asset

    async def update_asset(
        self,
        asset_id: int,
        update_data: dict[str, Any],
        *,
        tenant_id: int,
        actor_user_id: int,
    ) -> Asset:
        asset: Asset = await self._get_entity(Asset, asset_id, tenant_id=tenant_id)
        if "status" in update_data:
            update_data["status"] = AssetStatus(update_data["status"])
        metadata = update_data.pop("metadata_json", update_data.pop("metadata", None))
        if metadata is not None:
            update_data["metadata_json"] = metadata
        self._apply_dict(asset, update_data, exclude={"id", "external_id", "tenant_id"})
        asset.updated_by_id = actor_user_id
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    # ==================================================================
    # Template linkage methods
    # ==================================================================

    async def get_templates_for_asset_type(
        self,
        asset_type_id: int,
        tenant_id: int,
    ) -> list[AuditTemplate]:
        await self._get_entity(AssetType, asset_type_id, tenant_id=tenant_id)
        result = await self.db.execute(
            select(AuditTemplate)
            .join(TemplateAssetType, TemplateAssetType.template_id == AuditTemplate.id)
            .where(
                TemplateAssetType.asset_type_id == asset_type_id,
                or_(
                    AuditTemplate.tenant_id == tenant_id,
                    AuditTemplate.tenant_id.is_(None),
                ),
            )
        )
        return list(result.scalars().all())
