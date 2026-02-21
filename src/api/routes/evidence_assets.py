"""Evidence Asset API routes.

Provides endpoints for evidence asset management including:
- File upload with metadata
- Listing assets by source module/ID
- Linking assets to investigations
- Soft delete with audit trail
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.evidence_asset import (
    EvidenceAssetCreate,
    EvidenceAssetListResponse,
    EvidenceAssetResponse,
    EvidenceAssetUpdate,
    EvidenceAssetUploadResponse,
)
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.core.config import settings
from src.domain.models.evidence_asset import (
    EvidenceAsset,
    EvidenceAssetType,
    EvidenceRetentionPolicy,
    EvidenceSourceModule,
    EvidenceVisibility,
)
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter()

# Allowed content types for upload (security: content-type allowlist)
ALLOWED_CONTENT_TYPES = {
    # Images
    "image/jpeg": "photo",
    "image/png": "photo",
    "image/gif": "photo",
    "image/webp": "photo",
    "image/heic": "photo",
    "image/heif": "photo",
    # Videos
    "video/mp4": "video",
    "video/webm": "video",
    "video/quicktime": "video",
    # Documents
    "application/pdf": "pdf",
    "application/msword": "document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
    "application/vnd.ms-excel": "document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "document",
    # Audio
    "audio/mpeg": "audio",
    "audio/wav": "audio",
    "audio/ogg": "audio",
}

# Maximum file size: 50MB
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


async def validate_source_exists(
    source_module: str,
    source_id: int,
    db: AsyncSession,
) -> bool:
    """Validate that the source record exists.

    Returns True if exists, raises HTTPException if not.
    """
    # Map source module to model
    source_models = {
        EvidenceSourceModule.NEAR_MISS.value: "src.domain.models.near_miss:NearMiss",
        EvidenceSourceModule.ROAD_TRAFFIC_COLLISION.value: "src.domain.models.rta:RoadTrafficCollision",
        EvidenceSourceModule.COMPLAINT.value: "src.domain.models.complaint:Complaint",
        EvidenceSourceModule.INCIDENT.value: "src.domain.models.incident:Incident",
        EvidenceSourceModule.INVESTIGATION.value: "src.domain.models.investigation:InvestigationRun",
        EvidenceSourceModule.AUDIT.value: "src.domain.models.audit:AuditRun",
        EvidenceSourceModule.ACTION.value: None,  # Actions are polymorphic, skip validation
    }

    model_path = source_models.get(source_module)
    if model_path is None:
        # Skip validation for polymorphic types
        return True

    # Import the model dynamically
    module_path, class_name = model_path.split(":")
    module = __import__(module_path, fromlist=[class_name])
    model_class = getattr(module, class_name)

    await get_or_404(
        db,
        model_class,
        source_id,
        detail=f"Source {source_module} with ID {source_id} not found",
    )
    return True


@router.post(
    "/upload",
    response_model=EvidenceAssetUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_evidence_asset(
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(..., description="File to upload"),
    source_module: str = Form(..., description="Source module (near_miss, road_traffic_collision, etc.)"),
    source_id: int = Form(..., description="ID of the source record"),
    asset_type: Optional[str] = Form(None, description="Asset type (auto-detected if not provided)"),
    title: Optional[str] = Form(None, description="Asset title"),
    description: Optional[str] = Form(None, description="Asset description"),
    captured_at: Optional[str] = Form(None, description="When evidence was captured (ISO datetime)"),
    captured_by_role: Optional[str] = Form(None, description="Role of person who captured"),
    latitude: Optional[float] = Form(None, description="GPS latitude"),
    longitude: Optional[float] = Form(None, description="GPS longitude"),
    location_description: Optional[str] = Form(None, description="Location description"),
    visibility: str = Form("internal_customer", description="Visibility for customer packs"),
    contains_pii: bool = Form(False, description="Whether asset contains PII"),
    redaction_required: bool = Form(False, description="Whether redaction is required"),
):
    """Upload an evidence asset file with metadata.

    Validates:
    - Content type is allowed
    - File size is within limits
    - Source record exists
    - User has permission to attach evidence

    Stores file in blob storage and creates EvidenceAsset record.
    """
    # Validate source module
    try:
        source_module_enum = EvidenceSourceModule(source_module)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_SOURCE_MODULE",
                "message": f"Invalid source module: {source_module}",
                "details": {"valid_modules": [e.value for e in EvidenceSourceModule]},
            },
        )

    # Validate source exists
    await validate_source_exists(source_module, source_id, db)

    # Validate content type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_CONTENT_TYPE",
                "message": f"Content type {content_type} is not allowed",
                "details": {"allowed_types": list(ALLOWED_CONTENT_TYPES.keys())},
            },
        )

    # Auto-detect asset type from content type if not provided
    detected_asset_type = ALLOWED_CONTENT_TYPES.get(content_type, "other")
    final_asset_type = asset_type or detected_asset_type

    # Validate asset type
    try:
        asset_type_enum = EvidenceAssetType(final_asset_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_ASSET_TYPE",
                "message": f"Invalid asset type: {final_asset_type}",
                "details": {"valid_types": [e.value for e in EvidenceAssetType]},
            },
        )

    # Read file content
    file_content = await file.read()
    file_size = len(file_content)

    # Validate file size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "FILE_TOO_LARGE",
                "message": f"File size {file_size} bytes exceeds maximum {MAX_FILE_SIZE_BYTES} bytes",
                "details": {"file_size": file_size, "max_size": MAX_FILE_SIZE_BYTES},
            },
        )

    # Calculate checksum
    checksum = hashlib.sha256(file_content).hexdigest()

    # Generate storage key
    # Format: {source_module}/{source_id}/{uuid}_{original_filename}
    file_uuid = str(uuid.uuid4())
    safe_filename = (file.filename or "unnamed").replace("/", "_").replace("\\", "_")
    storage_key = f"evidence/{source_module}/{source_id}/{file_uuid}_{safe_filename}"

    # Upload to blob storage
    from src.infrastructure.storage import StorageError, storage_service

    try:
        await storage_service().upload(
            storage_key=storage_key,
            content=file_content,
            content_type=content_type,
            metadata={
                "source_module": source_module,
                "source_id": str(source_id),
                "uploaded_by": str(current_user.id),
            },
        )
    except StorageError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "STORAGE_UPLOAD_FAILED",
                "message": f"Failed to upload file to storage: {e}",
            },
        )

    # Parse captured_at if provided
    parsed_captured_at = None
    if captured_at:
        try:
            parsed_captured_at = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        except ValueError:
            pass  # Ignore invalid datetime

    # Validate visibility
    try:
        visibility_enum = EvidenceVisibility(visibility)
    except ValueError:
        visibility_enum = EvidenceVisibility.INTERNAL_CUSTOMER

    # Create EvidenceAsset record
    evidence_asset = EvidenceAsset(
        storage_key=storage_key,
        original_filename=file.filename,
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
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )

    db.add(evidence_asset)
    await db.commit()
    await db.refresh(evidence_asset)
    await invalidate_tenant_cache(current_user.tenant_id, "evidence_assets")
    track_metric("evidence.mutation", 1)

    return EvidenceAssetUploadResponse(
        id=evidence_asset.id,
        storage_key=evidence_asset.storage_key,
        original_filename=evidence_asset.original_filename or "unnamed",
        content_type=evidence_asset.content_type,
        file_size_bytes=evidence_asset.file_size_bytes or 0,
        message="File uploaded successfully",
    )


@router.get("/", response_model=EvidenceAssetListResponse)
async def list_evidence_assets(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    source_module: Optional[str] = Query(None, description="Filter by source module"),
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    asset_type: Optional[str] = Query(None, description="Filter by asset type"),
    linked_investigation_id: Optional[int] = Query(None, description="Filter by linked investigation"),
    include_deleted: bool = Query(False, description="Include soft-deleted assets"),
):
    """List evidence assets with filtering and pagination.

    Returns assets in deterministic order (created_at DESC, id ASC).
    Excludes soft-deleted assets by default.
    """
    query = select(EvidenceAsset).where(EvidenceAsset.tenant_id == current_user.tenant_id)

    if not include_deleted:
        query = query.where(EvidenceAsset.deleted_at.is_(None))

    if source_module:
        try:
            source_module_enum = EvidenceSourceModule(source_module)
            query = query.where(EvidenceAsset.source_module == source_module_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_SOURCE_MODULE",
                    "message": f"Invalid source module: {source_module}",
                    "details": {"valid_modules": [e.value for e in EvidenceSourceModule]},
                },
            )

    if source_id is not None:
        query = query.where(EvidenceAsset.source_id == source_id)

    if asset_type:
        try:
            asset_type_enum = EvidenceAssetType(asset_type)
            query = query.where(EvidenceAsset.asset_type == asset_type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_ASSET_TYPE",
                    "message": f"Invalid asset type: {asset_type}",
                    "details": {"valid_types": [e.value for e in EvidenceAssetType]},
                },
            )

    if linked_investigation_id is not None:
        query = query.where(EvidenceAsset.linked_investigation_id == linked_investigation_id)

    query = query.order_by(EvidenceAsset.created_at.desc(), EvidenceAsset.id.asc())

    return await paginate(db, query, params)


@router.get("/{asset_id}", response_model=EvidenceAssetResponse)
async def get_evidence_asset(
    asset_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific evidence asset by ID."""
    query = select(EvidenceAsset).where(
        EvidenceAsset.id == asset_id,
        EvidenceAsset.deleted_at.is_(None),
    )
    result = await db.execute(query)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "ASSET_NOT_FOUND",
                "message": f"Evidence asset with ID {asset_id} not found",
                "details": {"asset_id": asset_id},
            },
        )

    return asset


@router.patch("/{asset_id}", response_model=EvidenceAssetResponse)
async def update_evidence_asset(
    asset_id: int,
    asset_data: EvidenceAssetUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update evidence asset metadata."""
    query = select(EvidenceAsset).where(
        EvidenceAsset.id == asset_id,
        EvidenceAsset.deleted_at.is_(None),
    )
    result = await db.execute(query)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "ASSET_NOT_FOUND",
                "message": f"Evidence asset with ID {asset_id} not found",
                "details": {"asset_id": asset_id},
            },
        )

    # Update fields
    update_data = asset_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "visibility" and value is not None:
            setattr(asset, field, EvidenceVisibility(value))
        elif field == "retention_policy" and value is not None:
            setattr(asset, field, EvidenceRetentionPolicy(value))
        else:
            setattr(asset, field, value)

    asset.updated_by_id = current_user.id

    await db.commit()
    await db.refresh(asset)
    await invalidate_tenant_cache(current_user.tenant_id, "evidence_assets")
    track_metric("evidence.mutation", 1)

    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence_asset(
    asset_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
):
    """Soft delete an evidence asset.

    Sets deleted_at and deleted_by_id for audit trail.
    Does not physically delete the file from blob storage.
    """
    query = select(EvidenceAsset).where(
        EvidenceAsset.id == asset_id,
        EvidenceAsset.deleted_at.is_(None),
    )
    result = await db.execute(query)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "ASSET_NOT_FOUND",
                "message": f"Evidence asset with ID {asset_id} not found",
                "details": {"asset_id": asset_id},
            },
        )

    # Soft delete
    asset.deleted_at = datetime.now(timezone.utc)
    asset.deleted_by_id = current_user.id
    asset.updated_by_id = current_user.id

    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "evidence_assets")
    track_metric("evidence.mutation", 1)

    return None


@router.post("/{asset_id}/link-investigation", response_model=EvidenceAssetResponse)
async def link_asset_to_investigation(
    asset_id: int,
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Link an evidence asset to an investigation.

    Used when creating an investigation from a source record to
    carry forward existing evidence assets.
    """
    # Get asset
    asset_query = select(EvidenceAsset).where(
        EvidenceAsset.id == asset_id,
        EvidenceAsset.deleted_at.is_(None),
    )
    result = await db.execute(asset_query)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "ASSET_NOT_FOUND",
                "message": f"Evidence asset with ID {asset_id} not found",
            },
        )

    from src.domain.models.investigation import InvestigationRun

    await get_or_404(db, InvestigationRun, investigation_id)

    # Link asset to investigation
    asset.linked_investigation_id = investigation_id
    asset.updated_by_id = current_user.id

    await db.commit()
    await db.refresh(asset)

    return asset


@router.get("/{asset_id}/signed-url")
async def get_signed_download_url(
    asset_id: int,
    db: DbSession,
    current_user: CurrentUser,
    expires_in: int = Query(3600, ge=60, le=86400, description="URL expiry in seconds (1min to 24hrs)"),
):
    """Get a signed URL for downloading an evidence asset.

    Returns a time-limited signed URL for secure download.
    """
    # Get asset
    query = select(EvidenceAsset).where(
        EvidenceAsset.id == asset_id,
        EvidenceAsset.deleted_at.is_(None),
    )
    result = await db.execute(query)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "ASSET_NOT_FOUND",
                "message": f"Evidence asset with ID {asset_id} not found",
            },
        )

    # Generate signed URL
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


@router.get("/download")
async def download_file_direct(
    key: str = Query(..., description="Storage key"),
    expires: int = Query(..., description="Expiry timestamp"),
    sig: str = Query(..., description="Signature"),
    cd: Optional[str] = Query(None, description="Content disposition"),
):
    """Direct download endpoint for local development signed URLs.

    Validates signature and serves file content.
    """
    import hmac as hmac_lib

    from fastapi.responses import Response

    from src.infrastructure.storage import LocalFileStorageService, StorageError, storage_service

    # Only allow this endpoint for local storage
    svc = storage_service()
    if not isinstance(svc, LocalFileStorageService):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "NOT_AVAILABLE",
                "message": "Direct download not available in production",
            },
        )

    # Validate expiry
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if expires < now_ts:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "URL_EXPIRED", "message": "Download URL has expired"},
        )

    # Validate signature
    message = f"{key}:{expires}"
    expected_sig = hmac_lib.new(
        settings.secret_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()[:16]

    if not hmac_lib.compare_digest(sig, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "INVALID_SIGNATURE",
                "message": "Invalid download signature",
            },
        )

    # Download and serve
    try:
        content = await svc.download(key)
    except StorageError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FILE_NOT_FOUND", "message": str(e)},
        )

    # Determine content type from file extension
    import mimetypes

    content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"

    headers = {}
    if cd:
        headers["Content-Disposition"] = cd

    return Response(content=content, media_type=content_type, headers=headers)
