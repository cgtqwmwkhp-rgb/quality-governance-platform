"""Asset Registry domain service.

Provides business logic and data access for asset types, assets,
locations, and template-asset-type linkages. All operations are tenant-scoped.

Assignment rule
---------------
Prefer assignment as **location XOR vehicle**: an asset may be assigned to a
``location_id`` *or* a ``vehicle_reg``, but not both at the same time. Setting
both raises ``BadRequestError``. Owner (``owner_user_id``) is independent of
this XOR rule. Changes to owner / location / vehicle append
``asset_assignment_events`` rows (append-only audit).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.asset import (
    Asset,
    AssetAssignmentEvent,
    AssetCategory,
    AssetStatus,
    AssetType,
    TemplateAssetType,
)
from src.domain.models.audit import AuditTemplate
from src.domain.models.location import Location, LocationKind

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


_EXPIRY_BANDS = frozenset({"overdue", "due_30", "due_60", "due_90"})


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
        stmt: Any = select(model).where(model_any.id == entity_id)
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

    @staticmethod
    def _assert_location_xor_vehicle(
        location_id: int | None,
        vehicle_reg: str | None,
    ) -> None:
        """Enforce location XOR vehicle assignment (not both).

        Owner is independent. Empty/blank vehicle_reg is treated as unset.
        """
        reg = (vehicle_reg or "").strip() or None
        if location_id is not None and reg is not None:
            raise BadRequestError(
                "Asset assignment must be location XOR vehicle: " "set location_id or vehicle_reg, not both"
            )

    @staticmethod
    def _normalize_vehicle_reg(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _record_assignment_event(
        self,
        *,
        asset: Asset,
        tenant_id: int,
        actor_user_id: int,
        from_location_id: int | None,
        to_location_id: int | None,
        from_vehicle_reg: str | None,
        to_vehicle_reg: str | None,
        from_owner_user_id: int | None,
        to_owner_user_id: int | None,
        note: str | None = None,
    ) -> None:
        if (
            from_location_id == to_location_id
            and from_vehicle_reg == to_vehicle_reg
            and from_owner_user_id == to_owner_user_id
        ):
            return
        self.db.add(
            AssetAssignmentEvent(
                asset_id=asset.id,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                from_location_id=from_location_id,
                to_location_id=to_location_id,
                from_vehicle_reg=from_vehicle_reg,
                to_vehicle_reg=to_vehicle_reg,
                from_owner_user_id=from_owner_user_id,
                to_owner_user_id=to_owner_user_id,
                note=note,
            )
        )

    # ==================================================================
    # Location methods
    # ==================================================================

    async def list_locations(
        self,
        tenant_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
        kind: str | None = None,
        is_active: bool | None = None,
        parent_id: int | None = None,
        search: str | None = None,
    ) -> PaginatedResult:
        query = select(Location).where(Location.tenant_id == tenant_id)
        if kind is not None:
            try:
                query = query.where(Location.kind == LocationKind(kind))
            except ValueError:
                pass
        if is_active is not None:
            query = query.where(Location.is_active == is_active)
        if parent_id is not None:
            query = query.where(Location.parent_id == parent_id)
        if search:
            query = query.where(Location.name.ilike(f"%{search}%"))
        query = query.order_by(Location.kind, Location.name)
        return await self._paginate(query, page, page_size)

    async def create_location(
        self,
        data: dict[str, Any],
        *,
        user_id: int,
        tenant_id: int,
        force: bool = False,
    ) -> Location:
        from src.domain.exceptions import ConflictError, ValidationError
        from src.domain.services.lookup_similarity import classify_lookup_name

        payload = {k: v for k, v in data.items() if k != "force"}
        name = str(payload.get("name") or "").strip()
        existing_rows = list(
            (
                await self.db.execute(
                    select(Location).where(
                        Location.tenant_id == tenant_id,
                        or_(Location.is_active.is_(True), Location.approval_status == "pending"),
                    )
                )
            )
            .scalars()
            .all()
        )
        intent, exact, similar = classify_lookup_name(name, [(row.id, row.name) for row in existing_rows])
        if intent == "reuse" and exact is not None:
            raise ConflictError(
                f"Location '{name}' already exists as '{exact[1]}'",
                details={"reuse_id": exact[0], "reuse_name": exact[1]},
            )
        if intent == "similar" and not force:
            raise ValidationError(
                f"Location '{name}' is similar to existing entries; pass force=true to create anyway",
                code="SIMILAR_LOOKUP",
                details={"similar_matches": [{"id": m.id, "name": m.name, "score": m.score} for m in similar]},
            )
        if "kind" in payload:
            payload["kind"] = LocationKind(payload["kind"])
        location = Location(
            **payload,
            created_by_id=user_id,
            updated_by_id=user_id,
            tenant_id=tenant_id,
        )
        self.db.add(location)
        await self.db.commit()
        await self.db.refresh(location)
        return location

    async def get_location(self, location_id: int, tenant_id: int) -> Location:
        return await self._get_entity(Location, location_id, tenant_id=tenant_id)

    async def update_location(
        self,
        location_id: int,
        update_data: dict[str, Any],
        *,
        tenant_id: int,
        actor_user_id: int,
    ) -> Location:
        location: Location = await self._get_entity(Location, location_id, tenant_id=tenant_id)
        if "kind" in update_data:
            update_data["kind"] = LocationKind(update_data["kind"])
        self._apply_dict(location, update_data, exclude={"id", "tenant_id"})
        location.updated_by_id = actor_user_id
        await self.db.commit()
        await self.db.refresh(location)
        return location

    async def delete_location(self, location_id: int, *, tenant_id: int) -> None:
        location: Location = await self._get_entity(Location, location_id, tenant_id=tenant_id)
        await self.db.delete(location)
        await self.db.commit()

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
        force: bool = False,
    ) -> AssetType:
        from src.domain.exceptions import ConflictError, ValidationError
        from src.domain.services.lookup_similarity import classify_lookup_name

        payload = {k: v for k, v in data.items() if k != "force"}
        name = str(payload.get("name") or "").strip()
        existing_rows = list(
            (
                await self.db.execute(
                    select(AssetType).where(
                        or_(AssetType.tenant_id == tenant_id, AssetType.tenant_id.is_(None)),
                        or_(AssetType.is_active.is_(True), AssetType.approval_status == "pending"),
                    )
                )
            )
            .scalars()
            .all()
        )
        intent, exact, similar = classify_lookup_name(name, [(row.id, row.name) for row in existing_rows])
        if intent == "reuse" and exact is not None:
            raise ConflictError(
                f"Asset type '{name}' already exists as '{exact[1]}'",
                details={"reuse_id": exact[0], "reuse_name": exact[1]},
            )
        if intent == "similar" and not force:
            raise ValidationError(
                f"Asset type '{name}' is similar to existing entries; pass force=true to create anyway",
                code="SIMILAR_LOOKUP",
                details={"similar_matches": [{"id": m.id, "name": m.name, "score": m.score} for m in similar]},
            )
        if "category" in payload:
            payload["category"] = AssetCategory(payload["category"])
        asset_type = AssetType(
            **payload,
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
        location_id: int | None = None,
        vehicle_reg: str | None = None,
        owner_user_id: int | None = None,
        expiry_band: str | None = None,
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
        if location_id is not None:
            query = query.where(Asset.location_id == location_id)
        if vehicle_reg is not None:
            query = query.where(Asset.vehicle_reg.ilike(vehicle_reg.strip()))
        if owner_user_id is not None:
            query = query.where(Asset.owner_user_id == owner_user_id)
        if expiry_band is not None and expiry_band in _EXPIRY_BANDS:
            now = datetime.now(timezone.utc)
            if expiry_band == "overdue":
                query = query.where(Asset.expiry_date.is_not(None), Asset.expiry_date < now)
            else:
                days = {"due_30": 30, "due_60": 60, "due_90": 90}[expiry_band]
                end = now + timedelta(days=days)
                query = query.where(
                    Asset.expiry_date.is_not(None),
                    Asset.expiry_date >= now,
                    Asset.expiry_date <= end,
                )
        query = query.order_by(Asset.asset_number)
        return await self._paginate(query, page, page_size)

    async def create_asset(
        self,
        data: dict[str, Any],
        *,
        user_id: int,
        tenant_id: int,
        commit: bool = True,
    ) -> Asset:
        if "status" in data:
            data["status"] = AssetStatus(data["status"])
        metadata = data.pop("metadata_json", data.pop("metadata", None))
        if metadata is not None:
            data["metadata_json"] = metadata
        if "vehicle_reg" in data:
            data["vehicle_reg"] = self._normalize_vehicle_reg(data["vehicle_reg"])
        self._assert_location_xor_vehicle(data.get("location_id"), data.get("vehicle_reg"))
        asset = Asset(
            **data,
            created_by_id=user_id,
            updated_by_id=user_id,
            tenant_id=tenant_id,
        )
        self.db.add(asset)
        await self.db.flush()
        if asset.location_id is not None or asset.vehicle_reg is not None or asset.owner_user_id is not None:
            self._record_assignment_event(
                asset=asset,
                tenant_id=tenant_id,
                actor_user_id=user_id,
                from_location_id=None,
                to_location_id=asset.location_id,
                from_vehicle_reg=None,
                to_vehicle_reg=asset.vehicle_reg,
                from_owner_user_id=None,
                to_owner_user_id=asset.owner_user_id,
                note="initial assignment",
            )
        if commit:
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
        commit: bool = True,
    ) -> Asset:
        asset: Asset = await self._get_entity(Asset, asset_id, tenant_id=tenant_id)
        if "status" in update_data:
            update_data["status"] = AssetStatus(update_data["status"])
        metadata = update_data.pop("metadata_json", update_data.pop("metadata", None))
        if metadata is not None:
            update_data["metadata_json"] = metadata
        if "vehicle_reg" in update_data:
            update_data["vehicle_reg"] = self._normalize_vehicle_reg(update_data["vehicle_reg"])

        from_location_id = asset.location_id
        from_vehicle_reg = asset.vehicle_reg
        from_owner_user_id = asset.owner_user_id

        effective_location = update_data["location_id"] if "location_id" in update_data else asset.location_id
        effective_vehicle = update_data["vehicle_reg"] if "vehicle_reg" in update_data else asset.vehicle_reg
        self._assert_location_xor_vehicle(effective_location, effective_vehicle)

        self._apply_dict(asset, update_data, exclude={"id", "external_id", "tenant_id"})
        asset.updated_by_id = actor_user_id

        self._record_assignment_event(
            asset=asset,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            from_location_id=from_location_id,
            to_location_id=asset.location_id,
            from_vehicle_reg=from_vehicle_reg,
            to_vehicle_reg=asset.vehicle_reg,
            from_owner_user_id=from_owner_user_id,
            to_owner_user_id=asset.owner_user_id,
        )

        if commit:
            await self.db.commit()
            await self.db.refresh(asset)
        else:
            await self.db.flush()
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
