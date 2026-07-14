"""Read-only asset health analytics endpoints."""

from fastapi import APIRouter

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.asset import AssetHealthSummaryResponse
from src.domain.services.asset_health_analytics_service import AssetHealthAnalyticsService

router = APIRouter()


def _tid(user: CurrentUser) -> int:
    tenant_id = user.tenant_id
    assert tenant_id is not None, "Tenant context required"
    return tenant_id


@router.get("/summary", response_model=AssetHealthSummaryResponse)
async def get_asset_health_summary(
    db: DbSession,
    user: CurrentUser,
) -> AssetHealthSummaryResponse:
    """Return tenant-scoped asset counts by expiry band, type, and status."""

    summary = await AssetHealthAnalyticsService(db).get_summary(_tid(user))
    return AssetHealthSummaryResponse.model_validate(summary)
