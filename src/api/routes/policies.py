"""Policy Library API routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func as sa_func
from sqlalchemy import select

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.policy import PolicyCreate, PolicyListResponse, PolicyResponse, PolicyUpdate
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.policy import Policy
from src.domain.services.audit_service import record_audit_event

router = APIRouter()


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new policy",
)
async def create_policy(
    policy_data: PolicyCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> Policy:
    """
    Create a new policy document.

    Requires authentication.
    """
    # Generate or use provided reference number
    if policy_data.reference_number:
        # Guard: Only authorized users can set explicit reference numbers
        if not current_user.has_permission("policy:set_reference_number"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission 'policy:set_reference_number' required to set explicit reference number",
            )

        reference_number = policy_data.reference_number
        # Check for duplicate reference number
        existing = await db.execute(select(Policy).where(Policy.reference_number == reference_number))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Policy with reference number {reference_number} already exists",
            )
    else:
        # Generate reference number (format: POL-YYYY-NNNN)
        year = datetime.now(timezone.utc).year
        count_result = await db.execute(select(sa_func.count()).select_from(Policy))
        count = count_result.scalar_one()
        reference_number = f"POL-{year}-{count + 1:04d}"

    # Create new policy
    policy = Policy(
        title=policy_data.title,
        description=policy_data.description,
        document_type=policy_data.document_type,
        status=policy_data.status,
        reference_number=reference_number,
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
        action="create",
        payload=policy_data.model_dump(mode="json"),
        user_id=current_user.id,
        request_id=request_id,
    )

    return policy


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Get a policy by ID",
)
async def get_policy(
    policy_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Policy:
    """
    Get a specific policy by ID.

    Requires authentication.
    """
    return await get_or_404(db, Policy, policy_id)


@router.get(
    "",
    response_model=PolicyListResponse,
    summary="List all policies",
)
async def list_policies(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
) -> PolicyListResponse:
    """
    List all policies with deterministic ordering.

    Policies are ordered by:
    1. reference_number DESC (newest first)
    2. id ASC (stable secondary sort)

    Requires authentication.
    """
    query = select(Policy).order_by(Policy.reference_number.desc(), Policy.id.asc())

    return await paginate(db, query, params)


@router.put(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Update a policy",
)
async def update_policy(
    policy_id: int,
    policy_data: PolicyUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> Policy:
    """
    Update an existing policy.

    Requires authentication.
    """
    policy = await get_or_404(db, Policy, policy_id)

    update_data = apply_updates(policy, policy_data, set_updated_at=False)

    policy.updated_by_id = current_user.id

    await db.commit()
    await db.refresh(policy)

    # Record audit event
    await record_audit_event(
        db=db,
        event_type="policy.updated",
        entity_type="policy",
        entity_id=str(policy.id),
        action="update",
        payload=update_data,
        user_id=current_user.id,
        request_id=request_id,
    )

    return policy


@router.delete(
    "/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a policy",
)
async def delete_policy(
    policy_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
    request_id: str = Depends(get_request_id),
) -> None:
    """
    Delete a policy.

    Requires authentication.
    """
    policy = await get_or_404(db, Policy, policy_id)

    # Record audit event
    await record_audit_event(
        db=db,
        event_type="policy.deleted",
        entity_type="policy",
        entity_id=str(policy.id),
        action="delete",
        payload={"policy_id": policy_id, "title": policy.title},
        user_id=current_user.id,
        request_id=request_id,
    )
    await db.delete(policy)
    await db.commit()
