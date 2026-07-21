"""Approve / merge / reject provisional Safety AssetType and Location lookups."""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.asset import Asset, AssetType
from src.domain.models.location import Location
from src.domain.services.lookup_similarity import classify_lookup_name, find_similar_matches

Kind = Literal["asset_type", "location"]


class SafetyLookupApprovalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_pending(self, *, tenant_id: int) -> dict[str, Any]:
        types = list(
            (
                await self.db.execute(
                    select(AssetType).where(
                        AssetType.tenant_id == tenant_id,
                        AssetType.approval_status == "pending",
                    )
                )
            )
            .scalars()
            .all()
        )
        locations = list(
            (
                await self.db.execute(
                    select(Location).where(
                        Location.tenant_id == tenant_id,
                        Location.approval_status == "pending",
                    )
                )
            )
            .scalars()
            .all()
        )
        active_types = list(
            (
                await self.db.execute(
                    select(AssetType).where(
                        or_(AssetType.tenant_id == tenant_id, AssetType.tenant_id.is_(None)),
                        AssetType.is_active.is_(True),
                        AssetType.approval_status == "approved",
                    )
                )
            )
            .scalars()
            .all()
        )
        active_locations = list(
            (
                await self.db.execute(
                    select(Location).where(
                        Location.tenant_id == tenant_id,
                        Location.is_active.is_(True),
                        Location.approval_status == "approved",
                    )
                )
            )
            .scalars()
            .all()
        )
        type_candidates = [(t.id, t.name) for t in active_types]
        location_candidates = [(loc.id, loc.name) for loc in active_locations]

        def serialize_type(item: AssetType) -> dict[str, Any]:
            similar = find_similar_matches(item.name, type_candidates)
            return {
                "kind": "asset_type",
                "id": item.id,
                "name": item.name,
                "source": item.source,
                "is_active": item.is_active,
                "approval_status": item.approval_status,
                "similar_matches": [{"id": m.id, "name": m.name, "score": m.score} for m in similar],
                "created_at": item.created_at,
            }

        def serialize_location(item: Location) -> dict[str, Any]:
            similar = find_similar_matches(item.name, location_candidates)
            return {
                "kind": "location",
                "id": item.id,
                "name": item.name,
                "source": item.source,
                "is_active": item.is_active,
                "approval_status": item.approval_status,
                "similar_matches": [{"id": m.id, "name": m.name, "score": m.score} for m in similar],
                "created_at": item.created_at,
            }

        items = [serialize_type(t) for t in types] + [serialize_location(loc) for loc in locations]
        items.sort(key=lambda row: (row["kind"], row["name"].lower(), row["id"]))
        return {"items": items, "total": len(items)}

    async def _get_pending(self, kind: Kind, entity_id: int, *, tenant_id: int) -> AssetType | Location:
        if kind == "asset_type":
            asset_type = (
                await self.db.execute(
                    select(AssetType).where(
                        AssetType.id == entity_id,
                        AssetType.tenant_id == tenant_id,
                        AssetType.approval_status == "pending",
                    )
                )
            ).scalar_one_or_none()
            if asset_type is None:
                raise NotFoundError(f"Pending {kind} {entity_id} not found")
            return asset_type
        location = (
            await self.db.execute(
                select(Location).where(
                    Location.id == entity_id,
                    Location.tenant_id == tenant_id,
                    Location.approval_status == "pending",
                )
            )
        ).scalar_one_or_none()
        if location is None:
            raise NotFoundError(f"Pending {kind} {entity_id} not found")
        return location

    async def approve(self, kind: Kind, entity_id: int, *, tenant_id: int, actor_user_id: int) -> dict[str, Any]:
        row = await self._get_pending(kind, entity_id, tenant_id=tenant_id)
        row.is_active = True
        row.approval_status = "approved"
        row.updated_by_id = actor_user_id
        await self.db.commit()
        return {"kind": kind, "id": entity_id, "approval_status": "approved", "is_active": True}

    async def merge(
        self,
        kind: Kind,
        entity_id: int,
        *,
        target_id: int,
        tenant_id: int,
        actor_user_id: int,
    ) -> dict[str, Any]:
        if target_id == entity_id:
            raise ValidationError("Cannot merge a lookup into itself")
        row = await self._get_pending(kind, entity_id, tenant_id=tenant_id)
        if kind == "asset_type":
            target_type = (
                await self.db.execute(
                    select(AssetType).where(
                        AssetType.id == target_id,
                        or_(AssetType.tenant_id == tenant_id, AssetType.tenant_id.is_(None)),
                        AssetType.approval_status == "approved",
                        AssetType.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if target_type is None:
                raise NotFoundError(f"Target asset type {target_id} not found or not an approved active type")
            await self.db.execute(
                update(Asset)
                .where(
                    Asset.asset_type_id == entity_id,
                    or_(Asset.tenant_id == tenant_id, Asset.tenant_id.is_(None)),
                )
                .values(asset_type_id=target_id, updated_by_id=actor_user_id)
            )
        else:
            target_location = (
                await self.db.execute(
                    select(Location).where(
                        Location.id == target_id,
                        Location.tenant_id == tenant_id,
                        Location.approval_status == "approved",
                        Location.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if target_location is None:
                raise NotFoundError(f"Target location {target_id} not found or not an approved active location")
            await self.db.execute(
                update(Asset)
                .where(
                    Asset.location_id == entity_id,
                    or_(Asset.tenant_id == tenant_id, Asset.tenant_id.is_(None)),
                )
                .values(location_id=target_id, updated_by_id=actor_user_id)
            )
        row.is_active = False
        row.approval_status = "rejected"
        row.updated_by_id = actor_user_id
        await self.db.commit()
        return {
            "kind": kind,
            "id": entity_id,
            "target_id": target_id,
            "approval_status": "rejected",
            "merged": True,
        }

    async def reject(
        self,
        kind: Kind,
        entity_id: int,
        *,
        target_id: int,
        tenant_id: int,
        actor_user_id: int,
    ) -> dict[str, Any]:
        # Reject requires remap to an existing lookup so assets are never left on a dead type.
        return await self.merge(
            kind,
            entity_id,
            target_id=target_id,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
        )

    async def preview_create(
        self,
        kind: Kind,
        name: str,
        *,
        tenant_id: int,
    ) -> dict[str, Any]:
        if kind == "asset_type":
            type_rows = list(
                (
                    await self.db.execute(
                        select(AssetType).where(
                            or_(AssetType.tenant_id == tenant_id, AssetType.tenant_id.is_(None)),
                        )
                    )
                )
                .scalars()
                .all()
            )
            candidates = [(row.id, row.name) for row in type_rows]
        else:
            location_rows = list(
                (
                    await self.db.execute(
                        select(Location).where(
                            Location.tenant_id == tenant_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            candidates = [(row.id, row.name) for row in location_rows]
        intent, exact, similar = classify_lookup_name(name, candidates)
        return {
            "kind": kind,
            "name": name,
            "intent": intent,
            "reuse_id": exact[0] if exact else None,
            "reuse_name": exact[1] if exact else None,
            "similar_matches": [{"id": m.id, "name": m.name, "score": m.score} for m in similar],
            "needs_confirmation": intent == "similar",
            "blocked_exact_duplicate": intent == "reuse",
        }
