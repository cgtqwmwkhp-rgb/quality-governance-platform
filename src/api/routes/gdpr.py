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
    dry_run: bool = Query(True, description="When True, preview the export without generating a final package"),
) -> dict:
    """Export all user data (Right of Access, GDPR Art. 15).

    Returns a JSON object containing all personal data associated with the user.
    When dry_run=True (the default) the response describes what *would* be
    exported without side-effects.
    """
    service = GDPRService(db, dry_run=dry_run)
    try:
        data = await service.export_user_data(current_user.id, current_user.tenant_id or 0)
        if dry_run:
            return {
                "dry_run": True,
                "message": "Preview of data that would be exported",
                "data": data,
            }
        return data
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/me/data-erasure")
async def request_data_erasure(
    db: DbSession,
    current_user: CurrentUser,
    reason: str = Query("", description="Optional reason for data erasure request"),
    confirm: bool = Query(False, description="Confirmation flag - must be True to proceed"),
    dry_run: bool = Query(True, description="When True, show what would be deleted without deleting"),
) -> dict:
    """Request data erasure (Right to Erasure, GDPR Art. 17).

    When dry_run=True (the default) the response describes which fields
    *would* be pseudonymized without modifying the database.

    To actually erase data, set both dry_run=false AND confirm=true.
    """
    if not dry_run and not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required. Set 'confirm=true' to proceed with data erasure.",
        )

    service = GDPRService(db, dry_run=dry_run)
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
    from sqlalchemy import select

    from src.domain.models.user import User

    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    import re

    _HEX64 = re.compile(r"^[0-9a-f]{64}$")

    def _looks_pseudonymized(val: str | None) -> bool:
        if not val:
            return False
        return bool(_HEX64.match(val)) or val == "REDACTED"

    is_anonymized = (
        (
            _looks_pseudonymized(user.email)
            or (user.email.startswith("deleted-") and user.email.endswith("@anonymized.local"))
        )
        and _looks_pseudonymized(user.first_name)
        and _looks_pseudonymized(user.last_name)
    )

    return {
        "user_id": current_user.id,
        "status": "completed" if is_anonymized else "not_requested",
        "is_anonymized": is_anonymized,
        "is_active": user.is_active,
    }
