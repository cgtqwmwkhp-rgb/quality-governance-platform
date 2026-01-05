"""API routes for the Policy Library."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func as sa_func
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.security import require_permission
from src.api.helpers import apply_pagination, pagination_params
from src.api.schemas.policy import PolicyCreate, PolicyListResponse, PolicyResponse, PolicyUpdate
from src.domain.models.policy import Policy
from src.domain.services.audit_service import record_audit_event
from src.api.schemas.policy import PolicyResponse

router = APIRouter()


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new policy",
)
async def create_policy(
    policy_data: PolicyCreate, db: DbSession, current_user: CurrentUser
) -> Policy:
    """
    Create a new policy document.

    A unique reference number is automatically generated.
    Requires authentication and `policy:create` permission.
    """
    # RBAC check
    await require_permission("policy:create")(current_user)

    # Generate reference number: POL-YYYY-NNNN
    year = datetime.now(timezone.utc).year
    count_query = select(sa_func.count()).select_from(Policy)
    result = await db.execute(count_query)
    count = result.scalar() or 0
    ref_num = f"POL-{year}-{count + 1:04d}"

    policy = Policy(
        **policy_data.model_dump(),
        reference_number=ref_num,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )

    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    # Record audit event
    await record_audit_event(
        db=db,
        event_type="policy.created",
        entity_type="policy",
        entity_id=str(policy.id),
        actor_user_id=current_user.id,
        after_value=PolicyResponse.model_validate(policy).model_dump(mode="json"),
    )

    return policy
