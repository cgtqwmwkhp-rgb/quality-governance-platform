"""GDPR compliance API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import CurrentUser, DbSession
from src.domain.exceptions import NotFoundError
from src.domain.services.gdpr_service import GDPRService

router = APIRouter(prefix="/gdpr", tags=["GDPR"])


@router.get("/me/data-export")
async def export_user_data(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Export all user data (Right of Access, GDPR Art. 15).

    Returns a JSON object containing all personal data associated with the user.
    """
    service = GDPRService(db)
    try:
        data = await service.export_user_data(current_user.id, current_user.tenant_id or 0)
        return data
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/me/data-erasure")
async def request_data_erasure(
    db: DbSession,
    current_user: CurrentUser,
    reason: str = Query("", description="Optional reason for data erasure request"),
    confirm: bool = Query(False, description="Confirmation flag - must be True to proceed"),
) -> dict:
    """Request data erasure (Right to Erasure, GDPR Art. 17).

    Requires confirmation parameter set to True.
    This will anonymize the user's personal data.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required. Set 'confirm=true' to proceed with data erasure.",
        )

    service = GDPRService(db)
    try:
        result = await service.request_erasure(current_user.id, current_user.tenant_id or 0, reason)
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/me/data-erasure/status")
async def get_erasure_status(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Get the status of any pending or completed data erasure request.

    Returns status information about the user's data erasure request.
    """
    from src.domain.models.user import User
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user data has been anonymized
    is_anonymized = (
        user.email.startswith("deleted-")
        and user.email.endswith("@anonymized.local")
        and user.first_name == "REDACTED"
        and user.last_name == "REDACTED"
    )

    return {
        "user_id": current_user.id,
        "status": "completed" if is_anonymized else "not_requested",
        "is_anonymized": is_anonymized,
        "is_active": user.is_active,
    }
