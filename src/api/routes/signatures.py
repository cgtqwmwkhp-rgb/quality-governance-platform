"""
Digital Signature API Routes

DocuSign-level e-signature capabilities.
"""

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.signatures import (
    DeclineSigningResponse,
    ExpireOldResponse,
    PendingRequestItem,
    SendRemindersResponse,
    SendRequestResponse,
    SignatureStatsResponse,
    SignDocumentResponse,
    SigningPageResponse,
    TemplateUseResponse,
    VoidRequestResponse,
)
from src.domain.models.user import User
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter()


# ============================================================================
# Schemas
# ============================================================================


class SignerInput(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    role: str = "signer"
    order: Optional[int] = None
    user_id: Optional[int] = None


class SignatureRequestCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    document_type: str = Field(..., min_length=1)
    document_id: Optional[str] = None
    workflow_type: str = Field(default="sequential", pattern="^(sequential|parallel)$")
    require_all: bool = True
    expires_in_days: int = Field(default=30, ge=1, le=365)
    reminder_frequency: int = Field(default=3, ge=0, le=30)
    signers: list[SignerInput] = Field(..., min_length=1)
    metadata: Optional[dict] = None


class SignatureRequestResponse(BaseModel):
    id: int
    reference_number: str
    title: str
    description: Optional[str]
    document_type: str
    workflow_type: str
    status: str
    expires_at: Optional[datetime]
    created_at: datetime
    completed_at: Optional[datetime]
    signers: list[dict]

    class Config:
        from_attributes = True


class SignerResponse(BaseModel):
    id: int
    email: str
    name: str
    signer_role: str
    order: int
    status: str
    signed_at: Optional[datetime]
    declined_at: Optional[datetime]

    class Config:
        from_attributes = True


class SignInput(BaseModel):
    signature_type: str = Field(..., pattern="^(drawn|typed|uploaded)$")
    signature_data: str = Field(..., min_length=1)
    auth_method: str = Field(default="email", pattern="^(email|sms|password|biometric)$")
    geo_location: Optional[str] = None


class DeclineInput(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    signer_roles: list[dict] = []
    signature_fields: list[dict] = []
    workflow_type: str = Field(default="sequential", pattern="^(sequential|parallel)$")
    expiry_days: int = Field(default=30, ge=1, le=365)
    reminder_days: int = Field(default=3, ge=0, le=30)


class TemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    signer_roles: list
    workflow_type: str
    expiry_days: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: int
    action: str
    actor_type: str
    actor_email: Optional[str]
    actor_name: Optional[str]
    details: dict
    created_at: datetime
    ip_address: Optional[str]

    class Config:
        from_attributes = True


# ============================================================================
# Signature Request Endpoints
# ============================================================================


@router.post("/requests", response_model=SignatureRequestResponse)
async def create_signature_request(
    data: SignatureRequestCreate,
    current_user: Annotated[User, Depends(require_permission("signature:create"))],
    db: DbSession,
):
    """Create a new signature request."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)

    tenant_id = current_user.tenant_id

    request = await service.create_request(
        tenant_id=tenant_id,
        title=data.title,
        initiated_by_id=current_user.id,
        document_type=data.document_type,
        document_id=data.document_id,
        description=data.description,
        workflow_type=data.workflow_type,
        require_all=data.require_all,
        expires_in_days=data.expires_in_days,
        reminder_frequency=data.reminder_frequency,
        signers=[s.model_dump() for s in data.signers],
        metadata=data.metadata,
    )

    await invalidate_tenant_cache(current_user.tenant_id, "signatures")
    track_metric("signature.mutation", 1)
    return _format_request(request)


@router.get("/requests", response_model=list[SignatureRequestResponse])
async def list_signature_requests(
    current_user: CurrentUser,
    db: DbSession,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """List signature requests."""
    from sqlalchemy.orm import selectinload

    from src.domain.models.digital_signature import SignatureRequest

    tenant_id = current_user.tenant_id

    stmt = (
        select(SignatureRequest)
        .options(selectinload(SignatureRequest.signers))
        .where(SignatureRequest.tenant_id == tenant_id)
    )

    if status:
        stmt = stmt.where(SignatureRequest.status == status)

    stmt = stmt.order_by(SignatureRequest.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    requests = result.scalars().unique().all()

    return [_format_request(r) for r in requests]


@router.get("/requests/pending", response_model=list[PendingRequestItem])
async def get_pending_requests(
    current_user: CurrentUser,
    db: DbSession,
):
    """Get signature requests pending user's signature."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)

    tenant_id = current_user.tenant_id

    requests = await service.get_pending_requests(
        tenant_id=tenant_id,
        user_id=current_user.id,
        email=current_user.email,
    )

    return [_format_request(r) for r in requests]


@router.get("/requests/{request_id}", response_model=SignatureRequestResponse)
async def get_signature_request(
    request_id: int,
    current_user: CurrentUser,
    db: DbSession,
):
    """Get a signature request by ID."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)
    request = await service.get_request(request_id)

    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return _format_request(request)


@router.post("/requests/{request_id}/send", response_model=SendRequestResponse)
async def send_signature_request(
    request_id: int,
    current_user: Annotated[User, Depends(require_permission("signature:update"))],
    db: DbSession,
):
    """Send a signature request to signers."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)

    try:
        request = await service.send_request(request_id)
        await invalidate_tenant_cache(request.tenant_id, "signatures")
        track_metric("signature.mutation", 1)
        return {"status": "sent", "reference": request.reference_number}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)


@router.post("/requests/{request_id}/void", response_model=VoidRequestResponse)
async def void_signature_request(
    request_id: int,
    current_user: Annotated[User, Depends(require_permission("signature:update"))],
    db: DbSession,
    reason: Optional[str] = None,
):
    """Void a signature request."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)

    try:
        request = await service.void_request(request_id, current_user.id, reason)
        await invalidate_tenant_cache(current_user.tenant_id, "signatures")
        track_metric("signature.mutation", 1)
        return {"status": "voided", "reference": request.reference_number}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)


@router.get("/requests/{request_id}/audit-log", response_model=list[AuditLogResponse])
async def get_audit_log(
    request_id: int,
    current_user: CurrentUser,
    db: DbSession,
):
    """Get audit log for a signature request."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)
    logs = await service.get_audit_log(request_id)

    return logs


# ============================================================================
# Signing Endpoints
# ============================================================================


@router.get("/sign/{token}", response_model=SigningPageResponse)
async def get_signing_page(
    token: str,
    request: Request,
    db: DbSession,
):
    """Get signing page data for external signer."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)
    signer = await service.get_signer_by_token(token)

    if not signer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    sig_request = signer.request

    await service.record_view(
        signer_id=signer.id,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown"),
    )

    return {
        "request": {
            "id": sig_request.id,
            "reference": sig_request.reference_number,
            "title": sig_request.title,
            "description": sig_request.description,
            "document_type": sig_request.document_type,
            "status": sig_request.status,
        },
        "signer": {
            "id": signer.id,
            "name": signer.name,
            "email": signer.email,
            "role": signer.signer_role,
            "status": signer.status,
        },
        "legal_statement": service.LEGAL_STATEMENT,
        "can_sign": signer.status in ["pending", "viewed"],
    }


@router.post("/sign/{token}", response_model=SignDocumentResponse)
async def sign_document(
    token: str,
    data: SignInput,
    request: Request,
    db: DbSession,
):
    """Apply signature to document."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)
    signer = await service.get_signer_by_token(token)

    if not signer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    try:
        signature = await service.sign(
            signer_id=signer.id,
            signature_type=data.signature_type,
            signature_data=data.signature_data,
            ip_address=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", "unknown"),
            auth_method=data.auth_method,
            geo_location=data.geo_location,
        )

        return {
            "status": "signed",
            "signature_id": signature.id,
            "signed_at": signature.signed_at.isoformat() if signature.signed_at else None,
            "request_status": signer.request.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)


@router.post("/sign/{token}/decline", response_model=DeclineSigningResponse)
async def decline_signing(
    token: str,
    data: DeclineInput,
    request: Request,
    db: DbSession,
):
    """Decline to sign."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)
    signer = await service.get_signer_by_token(token)

    if not signer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    try:
        signer = await service.decline(
            signer_id=signer.id,
            reason=data.reason,
            ip_address=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", "unknown"),
        )

        return {
            "status": "declined",
            "declined_at": signer.declined_at.isoformat() if signer.declined_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)


# ============================================================================
# Template Endpoints
# ============================================================================


@router.post("/templates", response_model=TemplateResponse)
async def create_template(
    data: TemplateCreate,
    current_user: Annotated[User, Depends(require_permission("signature:create"))],
    db: DbSession,
):
    """Create a signature template."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)

    tenant_id = current_user.tenant_id

    template = await service.create_template(
        tenant_id=tenant_id,
        name=data.name,
        created_by_id=current_user.id,
        description=data.description,
        signer_roles=data.signer_roles,
        signature_fields=data.signature_fields,
        workflow_type=data.workflow_type,
        expiry_days=data.expiry_days,
        reminder_days=data.reminder_days,
    )

    await invalidate_tenant_cache(current_user.tenant_id, "signatures")
    track_metric("signature.mutation", 1)
    return template


@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates(
    current_user: CurrentUser,
    db: DbSession,
):
    """List signature templates."""
    from src.domain.models.digital_signature import SignatureTemplate

    tenant_id = current_user.tenant_id

    stmt = (
        select(SignatureTemplate)
        .where(
            SignatureTemplate.tenant_id == tenant_id,
            SignatureTemplate.is_active == True,  # noqa: E712
        )
        .order_by(SignatureTemplate.name)
    )
    result = await db.execute(stmt)
    templates = result.scalars().all()

    return templates


@router.post("/templates/{template_id}/use", response_model=TemplateUseResponse)
async def use_template(
    template_id: int,
    signers: list[SignerInput],
    current_user: Annotated[User, Depends(require_permission("signature:create"))],
    db: DbSession,
    title: Optional[str] = None,
):
    """Create a signature request from a template."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)

    try:
        request = await service.create_from_template(
            template_id=template_id,
            initiated_by_id=current_user.id,
            signers=[s.model_dump() for s in signers],
            title=title,
        )

        return _format_request(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)


# ============================================================================
# Statistics Endpoints
# ============================================================================


@router.get("/stats", response_model=SignatureStatsResponse)
async def get_signature_stats(
    current_user: CurrentUser,
    db: DbSession,
):
    """Get signature statistics."""
    from src.domain.models.digital_signature import Signature, SignatureRequest

    tenant_id = current_user.tenant_id

    status_result = await db.execute(
        select(SignatureRequest.status, func.count(SignatureRequest.id))
        .where(SignatureRequest.tenant_id == tenant_id)
        .group_by(SignatureRequest.status)
    )
    status_counts: dict[str, int] = dict(status_result.all())

    total_signatures = await db.scalar(select(func.count(Signature.id)).where(Signature.tenant_id == tenant_id)) or 0

    this_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0)
    this_month_count = (
        await db.scalar(
            select(func.count(SignatureRequest.id)).where(
                SignatureRequest.tenant_id == tenant_id,
                SignatureRequest.created_at >= this_month_start,
            )
        )
        or 0
    )

    return {
        "requests_by_status": status_counts,
        "total_signatures": total_signatures,
        "requests_this_month": this_month_count,
    }


# ============================================================================
# Admin Endpoints
# ============================================================================


@router.post("/admin/send-reminders", response_model=SendRemindersResponse)
async def send_reminders(
    current_user: Annotated[User, Depends(require_permission("signature:update"))],
    db: DbSession,
):
    """Send reminders for pending signatures (admin/cron job)."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)

    tenant_id = current_user.tenant_id

    count = await service.send_reminders(tenant_id)

    return {"reminders_sent": count}


@router.post("/admin/expire-old", response_model=ExpireOldResponse)
async def expire_old_requests(
    current_user: Annotated[User, Depends(require_permission("signature:update"))],
    db: DbSession,
):
    """Expire old signature requests (admin/cron job)."""
    from src.domain.services.signature_service import SignatureService

    service = SignatureService(db)

    tenant_id = current_user.tenant_id

    count = await service.expire_old_requests(tenant_id)

    return {"expired_count": count}


# ============================================================================
# Helpers
# ============================================================================


def _format_request(request) -> dict:
    """Format a signature request for response."""
    return {
        "id": request.id,
        "reference_number": request.reference_number,
        "title": request.title,
        "description": request.description,
        "document_type": request.document_type,
        "workflow_type": request.workflow_type,
        "status": request.status,
        "expires_at": request.expires_at,
        "created_at": request.created_at,
        "completed_at": request.completed_at,
        "signers": [
            {
                "id": s.id,
                "email": s.email,
                "name": s.name,
                "role": s.signer_role,
                "order": s.order,
                "status": s.status,
                "signed_at": s.signed_at.isoformat() if s.signed_at else None,
                "declined_at": s.declined_at.isoformat() if s.declined_at else None,
            }
            for s in request.signers
        ],
    }
