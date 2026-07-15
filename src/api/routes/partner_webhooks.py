"""Partner webhook subscription API — Wave5 cash-in-wall scaffold.

Routes under /api/v1/partner-webhooks/*
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.partner_webhook import (
    PartnerWebhookEventCatalogResponse,
    WebhookDeliveryLogListResponse,
    WebhookDeliveryLogResponse,
    WebhookSubscriptionCreate,
    WebhookSubscriptionListResponse,
    WebhookSubscriptionResponse,
    WebhookSubscriptionUpdate,
)
from src.api.utils.errors import api_error
from src.api.utils.tenant import require_tenant_id
from src.domain.models.partner_webhook import PARTNER_WEBHOOK_EVENTS
from src.domain.models.user import User
from src.domain.services.partner_webhook_service import PartnerWebhookService

router = APIRouter()


def _tenant_id_for(user: User) -> int:
    return require_tenant_id(getattr(user, "tenant_id", None))


@router.get("/events", response_model=PartnerWebhookEventCatalogResponse)
async def list_event_catalog(
    current_user: CurrentUser,
) -> PartnerWebhookEventCatalogResponse:
    """Return supported partner webhook event types."""
    return PartnerWebhookEventCatalogResponse(events=list(PARTNER_WEBHOOK_EVENTS))


@router.post(
    "/subscriptions",
    response_model=WebhookSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    data: WebhookSubscriptionCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
) -> WebhookSubscriptionResponse:
    """Create a partner webhook subscription."""
    tenant_id = _tenant_id_for(current_user)
    service = PartnerWebhookService(db)
    subscription = await service.create_subscription(
        tenant_id=tenant_id,
        name=data.name,
        url=str(data.url),
        secret=data.secret,
        events=data.events,
        is_active=data.is_active,
    )
    return WebhookSubscriptionResponse.model_validate(subscription)


@router.get("/subscriptions", response_model=WebhookSubscriptionListResponse)
async def list_subscriptions(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> WebhookSubscriptionListResponse:
    """List partner webhook subscriptions for the current tenant."""
    tenant_id = _tenant_id_for(current_user)
    service = PartnerWebhookService(db)
    subscriptions = await service.list_subscriptions(tenant_id)
    paginated = subscriptions[skip : skip + limit]
    return WebhookSubscriptionListResponse(
        items=[WebhookSubscriptionResponse.model_validate(s) for s in paginated],
        total=len(subscriptions),
    )


@router.get("/subscriptions/{subscription_id}", response_model=WebhookSubscriptionResponse)
async def get_subscription(
    subscription_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> WebhookSubscriptionResponse:
    """Get a partner webhook subscription by id."""
    tenant_id = _tenant_id_for(current_user)
    service = PartnerWebhookService(db)
    subscription = await service.get_subscription(tenant_id, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Webhook subscription not found"),
        )
    return WebhookSubscriptionResponse.model_validate(subscription)


@router.patch("/subscriptions/{subscription_id}", response_model=WebhookSubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    data: WebhookSubscriptionUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
) -> WebhookSubscriptionResponse:
    """Update a partner webhook subscription."""
    tenant_id = _tenant_id_for(current_user)
    service = PartnerWebhookService(db)
    subscription = await service.get_subscription(tenant_id, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Webhook subscription not found"),
        )
    update_data = data.model_dump(exclude_unset=True)
    if "url" in update_data and update_data["url"] is not None:
        update_data["url"] = str(update_data["url"])
    subscription = await service.update_subscription(subscription, **update_data)
    return WebhookSubscriptionResponse.model_validate(subscription)


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
) -> None:
    """Delete a partner webhook subscription."""
    tenant_id = _tenant_id_for(current_user)
    service = PartnerWebhookService(db)
    subscription = await service.get_subscription(tenant_id, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Webhook subscription not found"),
        )
    await service.delete_subscription(subscription)


@router.get("/deliveries", response_model=WebhookDeliveryLogListResponse)
async def list_delivery_logs(
    db: DbSession,
    current_user: CurrentUser,
    subscription_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> WebhookDeliveryLogListResponse:
    """List partner webhook delivery logs for the current tenant."""
    tenant_id = _tenant_id_for(current_user)
    service = PartnerWebhookService(db)
    logs, total = await service.list_delivery_logs(
        tenant_id,
        subscription_id=subscription_id,
        skip=skip,
        limit=limit,
    )
    return WebhookDeliveryLogListResponse(
        items=[WebhookDeliveryLogResponse.model_validate(log) for log in logs],
        total=total,
    )
