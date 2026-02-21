"""Evidence asset domain service.

Extracts business logic from evidence_assets routes into a testable service class.
Covers upload, listing, linking, metadata updates, soft-delete, and signed-URL generation.
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.evidence_asset import (
    EvidenceAsset,
    EvidenceAssetType,
    EvidenceRetentionPolicy,
    EvidenceSourceModule,
    EvidenceVisibility,
)
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "photo",
    "image/png": "photo",
    "image/gif": "photo",
    "image/webp": "photo",
    "image/heic": "photo",
    "image/heif": "photo",
    "video/mp4": "video",
    "video/webm": "video",
    "video/quicktime": "video",
    "application/pdf": "pdf",
    "application/msword": "document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
    "application/vnd.ms-excel": "document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "document",
    "audio/mpeg": "audio",
    "audio/wav": "audio",
    "audio/ogg": "audio",
}

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


class EvidenceService:
    """Handles evidence asset upload, CRUD, linking, and signed-URL generation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Source validation
    # ------------------------------------------------------------------

    async def validate_source_exists(self, source_module: str, source_id: int) -> bool:
        """Validate that the source record exists.

        Raises:
            LookupError: If the source record is not found.
            ValueError: If the source module is invalid.
        """
        source_models = {
            EvidenceSourceModule.NEAR_MISS.value: "src.domain.models.near_miss:NearMiss",
            EvidenceSourceModule.ROAD_TRAFFIC_COLLISION.value: "src.domain.models.rta:RoadTrafficCollision",
            EvidenceSourceModule.COMPLAINT.value: "src.domain.models.complaint:Complaint",
            EvidenceSourceModule.INCIDENT.value: "src.domain.models.incident:Incident",
            EvidenceSourceModule.INVESTIGATION.value: "src.domain.models.investigation:InvestigationRun",
            EvidenceSourceModule.AUDIT.value: "src.domain.models.audit:AuditRun",
            EvidenceSourceModule.ACTION.value: None,
        }

        model_path = source_models.get(source_module)
        if model_path is None:
            return True

        module_path, class_name = model_path.split(":")
        module = __import__(module_path, fromlist=[class_name])
        model_class = getattr(module, class_name)

        result = await self.db.execute(select(model_class).where(model_class.id == source_id))
        if result.scalar_one_or_none() is None:
            raise LookupError(f"Source {source_module} with ID {source_id} not found")
        return True

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    async def upload(
        self,
        *,
        file_content: bytes,
        filename: str | None,
        content_type: str,
        source_module: str,
        source_id: int,
        user_id: int,
        tenant_id: int | None,
        asset_type: str | None = None,
        title: str | None = None,
        description: str | None = None,
        captured_at: str | None = None,
        captured_by_role: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        location_description: str | None = None,
        visibility: str = "internal_customer",
        contains_pii: bool = False,
        redaction_required: bool = False,
    ) -> EvidenceAsset:
        """Upload an evidence asset file with metadata.

        Raises:
            ValueError: For invalid source module, content type, asset type, or file too large.
            LookupError: If the source record doesn't exist.
            RuntimeError: If storage upload fails.
        """
        try:
            source_module_enum = EvidenceSourceModule(source_module)
        except ValueError:
            raise ValueError(
                f"Invalid source module: {source_module}. " f"Valid modules: {[e.value for e in EvidenceSourceModule]}"
            )

        await self.validate_source_exists(source_module, source_id)

        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(f"Content type {content_type} is not allowed")

        detected_asset_type = ALLOWED_CONTENT_TYPES.get(content_type, "other")
        final_asset_type = asset_type or detected_asset_type

        try:
            asset_type_enum = EvidenceAssetType(final_asset_type)
        except ValueError:
            raise ValueError(f"Invalid asset type: {final_asset_type}")

        file_size = len(file_content)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File size {file_size} bytes exceeds maximum {MAX_FILE_SIZE_BYTES} bytes")

        checksum = hashlib.sha256(file_content).hexdigest()

        file_uuid = str(uuid.uuid4())
        safe_filename = (filename or "unnamed").replace("/", "_").replace("\\", "_")
        storage_key = f"evidence/{source_module}/{source_id}/{file_uuid}_{safe_filename}"

        from src.infrastructure.storage import StorageError, storage_service

        try:
            await storage_service().upload(
                storage_key=storage_key,
                content=file_content,
                content_type=content_type,
                metadata={
                    "source_module": source_module,
                    "source_id": str(source_id),
                    "uploaded_by": str(user_id),
                },
            )
        except StorageError as e:
            raise RuntimeError(f"Failed to upload file to storage: {e}")

        parsed_captured_at = None
        if captured_at:
            try:
                parsed_captured_at = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            except ValueError:
                pass

        try:
            visibility_enum = EvidenceVisibility(visibility)
        except ValueError:
            visibility_enum = EvidenceVisibility.INTERNAL_CUSTOMER

        evidence_asset = EvidenceAsset(
            storage_key=storage_key,
            original_filename=filename,
            content_type=content_type,
            file_size_bytes=file_size,
            checksum_sha256=checksum,
            asset_type=asset_type_enum,
            source_module=source_module_enum,
            source_id=source_id,
            title=title,
            description=description,
            captured_at=parsed_captured_at,
            captured_by_role=captured_by_role,
            latitude=latitude,
            longitude=longitude,
            location_description=location_description,
            render_hint="thumbnail" if final_asset_type == "photo" else "link",
            visibility=visibility_enum,
            contains_pii=contains_pii,
            redaction_required=redaction_required,
            retention_policy=EvidenceRetentionPolicy.STANDARD,
            created_by_id=user_id,
            updated_by_id=user_id,
        )

        self.db.add(evidence_asset)
        await self.db.commit()
        await self.db.refresh(evidence_asset)
        await invalidate_tenant_cache(tenant_id, "evidence_assets")
        track_metric("evidence.mutation", 1)
        track_metric("evidence.uploaded", 1)

        return evidence_asset

    # ------------------------------------------------------------------
    # List / Get
    # ------------------------------------------------------------------

    async def list_assets(
        self,
        *,
        tenant_id: int | None,
        params: PaginationParams,
        source_module: str | None = None,
        source_id: int | None = None,
        asset_type: str | None = None,
        linked_investigation_id: int | None = None,
        include_deleted: bool = False,
    ):
        """List evidence assets with filtering and pagination.

        Raises:
            ValueError: For invalid source_module or asset_type filter values.
        """
        query = select(EvidenceAsset).where(EvidenceAsset.tenant_id == tenant_id)

        if not include_deleted:
            query = query.where(EvidenceAsset.deleted_at.is_(None))

        if source_module:
            try:
                source_module_enum = EvidenceSourceModule(source_module)
                query = query.where(EvidenceAsset.source_module == source_module_enum)
            except ValueError:
                raise ValueError(f"Invalid source module: {source_module}")

        if source_id is not None:
            query = query.where(EvidenceAsset.source_id == source_id)

        if asset_type:
            try:
                asset_type_enum = EvidenceAssetType(asset_type)
                query = query.where(EvidenceAsset.asset_type == asset_type_enum)
            except ValueError:
                raise ValueError(f"Invalid asset type: {asset_type}")

        if linked_investigation_id is not None:
            query = query.where(EvidenceAsset.linked_investigation_id == linked_investigation_id)

        query = query.order_by(EvidenceAsset.created_at.desc(), EvidenceAsset.id.asc())
        return await paginate(self.db, query, params)

    async def get_asset(self, asset_id: int) -> EvidenceAsset:
        """Get a specific evidence asset by ID (excludes soft-deleted).

        Raises:
            LookupError: If the asset is not found or deleted.
        """
        query = select(EvidenceAsset).where(
            EvidenceAsset.id == asset_id,
            EvidenceAsset.deleted_at.is_(None),
        )
        result = await self.db.execute(query)
        asset = result.scalar_one_or_none()
        if not asset:
            raise LookupError(f"Evidence asset with ID {asset_id} not found")
        return asset

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_asset(
        self,
        asset_id: int,
        asset_data: BaseModel,
        *,
        user_id: int,
        tenant_id: int | None,
    ) -> EvidenceAsset:
        """Update evidence asset metadata.

        Raises:
            LookupError: If the asset is not found or deleted.
        """
        asset = await self.get_asset(asset_id)

        _enum_fields = {"visibility", "retention_policy"}
        update_data = asset_data.model_dump(exclude_unset=True)
        if "visibility" in update_data and update_data["visibility"] is not None:
            asset.visibility = EvidenceVisibility(update_data["visibility"])
        if "retention_policy" in update_data and update_data["retention_policy"] is not None:
            asset.retention_policy = EvidenceRetentionPolicy(update_data["retention_policy"])

        apply_updates(asset, asset_data, exclude=_enum_fields)
        asset.updated_by_id = user_id

        await self.db.commit()
        await self.db.refresh(asset)
        await invalidate_tenant_cache(tenant_id, "evidence_assets")
        track_metric("evidence.mutation", 1)

        return asset

    # ------------------------------------------------------------------
    # Delete (soft)
    # ------------------------------------------------------------------

    async def delete_asset(
        self,
        asset_id: int,
        *,
        user_id: int,
        tenant_id: int | None,
    ) -> None:
        """Soft-delete an evidence asset.

        Raises:
            LookupError: If the asset is not found or already deleted.
        """
        asset = await self.get_asset(asset_id)
        asset.deleted_at = datetime.now(timezone.utc)
        asset.deleted_by_id = user_id
        asset.updated_by_id = user_id

        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "evidence_assets")
        track_metric("evidence.mutation", 1)

    # ------------------------------------------------------------------
    # Link to investigation
    # ------------------------------------------------------------------

    async def link_to_investigation(
        self,
        asset_id: int,
        investigation_id: int,
        *,
        user_id: int,
        tenant_id: int | None,
    ) -> EvidenceAsset:
        """Link an evidence asset to an investigation.

        Raises:
            LookupError: If the asset or investigation is not found.
        """
        asset = await self.get_asset(asset_id)

        from src.domain.models.investigation import InvestigationRun

        inv_result = await self.db.execute(
            select(InvestigationRun).where(
                InvestigationRun.id == investigation_id,
                InvestigationRun.tenant_id == tenant_id,
            )
        )
        if inv_result.scalar_one_or_none() is None:
            raise LookupError(f"Investigation with ID {investigation_id} not found")

        asset.linked_investigation_id = investigation_id
        asset.updated_by_id = user_id

        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    # ------------------------------------------------------------------
    # Signed URL
    # ------------------------------------------------------------------

    async def get_signed_url(
        self,
        asset_id: int,
        *,
        expires_in: int = 3600,
    ) -> dict[str, Any]:
        """Generate a signed download URL for an evidence asset.

        Raises:
            LookupError: If the asset is not found or deleted.
        """
        asset = await self.get_asset(asset_id)

        from src.infrastructure.storage import storage_service

        content_disposition = f'attachment; filename="{asset.original_filename or "download"}"'
        signed_url = storage_service().get_signed_url(
            storage_key=asset.storage_key,
            expires_in_seconds=expires_in,
            content_disposition=content_disposition,
        )

        return {
            "asset_id": asset_id,
            "signed_url": signed_url,
            "expires_in_seconds": expires_in,
            "content_type": asset.content_type,
            "filename": asset.original_filename,
        }
