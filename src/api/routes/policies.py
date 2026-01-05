"""Policy Library API routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.security import require_permission
from src.api.schemas.policy import PolicyCreate, PolicyListResponse, PolicyResponse, PolicyUpdate
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
) -> Policy:
    """
    Create a new policy document.

    Requires authentication and policy:create permission.
    """
    # Check permission
    await require_permission("policy:create", current_user, db)
    # Generate reference number (format: POL-YYYY-NNNN)
    year = datetime.now(timezone.utc).year

    # Get the count of policies created this year
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
    try:
        await db.commit()
        await db.refresh(policy)
    except IntegrityError as e:
        await db.rollback()
        # Check if it's a duplicate reference_number error
        if "reference_number" in str(e.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Policy with reference number {reference_number} already exists",
            )
        # Re-raise if it's a different integrity error
        raise

    # Record audit event
    await record_audit_event(
        db=db,
        event_type="policy.created",
        entity_type="policy",
        entity_id=str(policy.id),
        action="create",
        payload=policy_data.model_dump(mode="json"),
        user_id=current_user.id,
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
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with id {policy_id} not found",
        )

    return policy


@router.get(
    "",
    response_model=PolicyListResponse,
    summary="List all policies",
)
async def list_policies(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> PolicyListResponse:
    """
    List all policies with deterministic ordering.

    Policies are ordered by:
    1. reference_number DESC (newest first)
    2. id ASC (stable secondary sort)

    Requires authentication.
    """
    # Count total
    count_result = await db.execute(select(sa_func.count()).select_from(Policy))
    total = count_result.scalar_one()

    # Get paginated results with deterministic ordering
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Policy)
        .order_by(Policy.reference_number.desc(), Policy.id.asc())  # Deterministic ordering
        .limit(page_size)
        .offset(offset)
    )
    policies = result.scalars().all()

    import math

    return PolicyListResponse(
        items=[PolicyResponse.model_validate(p) for p in policies],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


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
) -> Policy:
    """
    Update an existing policy.

    Requires authentication.
    """
    # Get existing policy
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with id {policy_id} not found",
        )

    # Update fields
    update_data = policy_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(policy, field, value)

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
    current_user: CurrentUser,
) -> None:
    """
    Delete a policy.

    Requires authentication.
    """
    # Get existing policy
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with id {policy_id} not found",
        )

    # Record audit event
    await record_audit_event(
        db=db,
        event_type="policy.deleted",
        entity_type="policy",
        entity_id=str(policy.id),
        action="delete",
        payload={"policy_id": policy_id, "title": policy.title},
        user_id=current_user.id,
    )
    await db.delete(policy)
    await db.commit()
