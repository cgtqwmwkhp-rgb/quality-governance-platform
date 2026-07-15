"""Partner API token management — R6 scoped bearer credentials.

Routes under /api/v1/partner-auth/*
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.partner_auth import (
    PartnerApiTokenCreate,
    PartnerApiTokenCreateResponse,
    PartnerApiTokenListResponse,
    PartnerApiTokenResponse,
)
from src.api.utils.errors import api_error
from src.api.utils.tenant import require_tenant_id
from src.domain.models.user import User
from src.domain.services.partner_auth_service import PartnerAuthService

router = APIRouter()


def _tenant_id_for(user: User) -> int:
    return require_tenant_id(getattr(user, "tenant_id", None))


@router.post(
    "/tokens",
    response_model=PartnerApiTokenCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_partner_token(
    data: PartnerApiTokenCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
) -> PartnerApiTokenCreateResponse:
    """Create a partner API token. Plaintext secret is returned once."""
    tenant_id = _tenant_id_for(current_user)
    service = PartnerAuthService(db)
    try:
        token, raw_token = await service.create_token(
            tenant_id=tenant_id,
            name=data.name,
            scopes=data.scopes,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.VALIDATION_ERROR, str(exc)),
        ) from exc
    response = PartnerApiTokenCreateResponse.model_validate(token)
    response.token = raw_token
    return response


@router.get("/tokens", response_model=PartnerApiTokenListResponse)
async def list_partner_tokens(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
    include_revoked: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> PartnerApiTokenListResponse:
    """List partner API tokens for the current tenant."""
    tenant_id = _tenant_id_for(current_user)
    service = PartnerAuthService(db)
    tokens = await service.list_tokens(tenant_id, include_revoked=include_revoked)
    paginated = tokens[skip : skip + limit]
    return PartnerApiTokenListResponse(
        items=[PartnerApiTokenResponse.model_validate(t) for t in paginated],
        total=len(tokens),
    )


@router.delete("/tokens/{token_id}", response_model=PartnerApiTokenResponse)
async def revoke_partner_token(
    token_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
) -> PartnerApiTokenResponse:
    """Revoke a partner API token (idempotent)."""
    tenant_id = _tenant_id_for(current_user)
    service = PartnerAuthService(db)
    token = await service.get_token(tenant_id, token_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Partner API token not found"),
        )
    token = await service.revoke_token(token)
    return PartnerApiTokenResponse.model_validate(token)
