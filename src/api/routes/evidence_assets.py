"""Evidence Asset API routes.

Thin controller layer — all business logic lives in EvidenceService.
"""

import hashlib
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession, require_permission
from src.domain.exceptions import AuthorizationError, NotFoundError, ValidationError
from src.api.schemas.evidence_asset import (
    EvidenceAssetListResponse,
    EvidenceAssetResponse,
    EvidenceAssetUpdate,
    EvidenceAssetUploadResponse,
    FileDownloadMeta,
    SignedUrlResponse,
)
from src.api.utils.pagination import PaginationParams
from src.core.config import settings
from src.domain.models.user import User
from src.domain.services.evidence_service import EvidenceService

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


@router.post("/upload", response_model=EvidenceAssetUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence_asset(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("evidence:create"))],
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
    """Upload an evidence asset file with metadata."""
    _span = tracer.start_span("upload_evidence_asset") if tracer else None

    file_content = await file.read()
    content_type = file.content_type or "application/octet-stream"

    service = EvidenceService(db)
    try:
        evidence_asset = await service.upload(
            file_content=file_content,
            filename=file.filename,
            content_type=content_type,
            source_module=source_module,
            source_id=source_id,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            asset_type=asset_type,
            title=title,
            description=description,
            captured_at=captured_at,
            captured_by_role=captured_by_role,
            latitude=latitude,
            longitude=longitude,
            location_description=location_description,
            visibility=visibility,
            contains_pii=contains_pii,
            redaction_required=redaction_required,
        )
    except ValueError as e:
        raise ValidationError(str(e))
    except LookupError as e:
        raise NotFoundError(str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    if _span:
        _span.end()
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
    """List evidence assets with filtering and pagination."""
    service = EvidenceService(db)
    try:
        return await service.list_assets(
            tenant_id=current_user.tenant_id,
            params=params,
            source_module=source_module,
            source_id=source_id,
            asset_type=asset_type,
            linked_investigation_id=linked_investigation_id,
            include_deleted=include_deleted,
        )
    except ValueError as e:
        raise ValidationError(str(e))


@router.get("/{asset_id}", response_model=EvidenceAssetResponse)
async def get_evidence_asset(
    asset_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific evidence asset by ID."""
    service = EvidenceService(db)
    try:
        return await service.get_asset(asset_id)
    except LookupError:
        raise NotFoundError("Evidence asset not found")


@router.patch("/{asset_id}", response_model=EvidenceAssetResponse)
async def update_evidence_asset(
    asset_id: int,
    asset_data: EvidenceAssetUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("evidence:update"))],
):
    """Update evidence asset metadata."""
    service = EvidenceService(db)
    try:
        return await service.update_asset(
            asset_id,
            asset_data,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
    except LookupError:
        raise NotFoundError("Evidence asset not found")


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence_asset(
    asset_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
):
    """Soft delete an evidence asset."""
    service = EvidenceService(db)
    try:
        await service.delete_asset(asset_id, user_id=current_user.id, tenant_id=current_user.tenant_id)
    except LookupError:
        raise NotFoundError("Evidence asset not found")
    return None


@router.post("/{asset_id}/link-investigation", response_model=EvidenceAssetResponse)
async def link_asset_to_investigation(
    asset_id: int,
    investigation_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("evidence:update"))],
):
    """Link an evidence asset to an investigation."""
    service = EvidenceService(db)
    try:
        return await service.link_to_investigation(
            asset_id,
            investigation_id,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
    except LookupError as e:
        raise NotFoundError(str(e))


@router.get("/{asset_id}/signed-url", response_model=SignedUrlResponse)
async def get_signed_download_url(
    asset_id: int,
    db: DbSession,
    current_user: CurrentUser,
    expires_in: int = Query(3600, ge=60, le=86400, description="URL expiry in seconds (1min to 24hrs)"),
):
    """Get a signed URL for downloading an evidence asset."""
    service = EvidenceService(db)
    try:
        return await service.get_signed_url(asset_id, expires_in=expires_in)
    except LookupError:
        raise NotFoundError("Evidence asset not found")


@router.get("/download", response_model=FileDownloadMeta)
async def download_file_direct(
    key: str = Query(..., description="Storage key"),
    expires: int = Query(..., description="Expiry timestamp"),
    sig: str = Query(..., description="Signature"),
    cd: Optional[str] = Query(None, description="Content disposition"),
):
    """Direct download endpoint for local development signed URLs.

    Validates signature and serves file content. Only available with local storage.
    """
    import hmac as hmac_lib

    from fastapi.responses import Response

    from src.infrastructure.storage import LocalFileStorageService, StorageError, storage_service

    svc = storage_service()
    if not isinstance(svc, LocalFileStorageService):
        raise ValidationError("Direct download not available in production")

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if expires < now_ts:
        raise AuthorizationError("Download URL has expired")

    message = f"{key}:{expires}"
    expected_sig = hmac_lib.new(
        settings.secret_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()[:16]

    if not hmac_lib.compare_digest(sig, expected_sig):
        raise AuthorizationError("Invalid download signature")

    try:
        content = await svc.download(key)
    except StorageError as e:
        raise NotFoundError(str(e))

    import mimetypes

    content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"

    headers = {}
    if cd:
        headers["Content-Disposition"] = cd

    return Response(content=content, media_type=content_type, headers=headers)
