"""Ensure every QGP User has a linked Engineer person record (Person ≠ Login).

PAMS remains inbound-only. These helpers never write to PAMS.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.domain.models.engineer import Engineer
from src.domain.models.user import User

logger = logging.getLogger(__name__)


def display_name_for_user(user: User) -> str:
    full = (getattr(user, "full_name", None) or "").strip()
    if full:
        return full[:200]
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    combined = f"{first} {last}".strip()
    if combined:
        return combined[:200]
    return (user.email or f"User {user.id}")[:200]


def _adoptable_roster_row(candidates: list[Engineer], user: User, name: str) -> Optional[Engineer]:
    """Choose the roster row this login belongs to, or None to create a fresh one.

    Display names are not unique, so two unlinked rows sharing a name mean the name does
    not identify a person. Adopting one anyway hands the new account another employee's
    competency and assignment history, so refuse: an unlinked person record is visible and
    correctable, whereas a wrongly linked one is silent. Candidates arrive ordered so an
    active row outranks a retired one, which means a tie on ``is_active`` is exactly the
    case where the choice would be arbitrary.
    """
    if not candidates:
        return None

    best = candidates[0]
    if len(candidates) > 1 and bool(candidates[1].is_active) == bool(best.is_active):
        logger.warning(
            "engineer_user_link_ambiguous user_id=%s display_name=%r candidates=%s action=created_new",
            user.id,
            name,
            [candidate.id for candidate in candidates],
        )
        return None

    if not best.is_active:
        # Assignment requires an *active* linked person, so this login cannot yet be given
        # actions or own a case. Only the upstream roster can put that right.
        logger.warning(
            "engineer_user_link_inactive_roster_row engineer_id=%s user_id=%s not_assignable_until_reactivated",
            best.id,
            user.id,
        )
    return best


async def ensure_engineer_for_user_async(
    db: AsyncSession,
    user: User,
    *,
    tenant_id: Optional[int] = None,
) -> Engineer:
    """Link or create an Engineer for a newly created / existing User (async routes)."""
    effective_tenant = tenant_id if tenant_id is not None else user.tenant_id
    if effective_tenant is None:
        raise ValueError("tenant_id is required to ensure an engineer profile")

    existing = (await db.execute(select(Engineer).where(Engineer.user_id == user.id))).scalar_one_or_none()
    if existing is not None:
        return existing

    # Prefer an unlinked PAMS/roster row whose display_name matches the user.
    name = display_name_for_user(user)
    candidates = list(
        (
            await db.execute(
                select(Engineer)
                .where(
                    Engineer.tenant_id == effective_tenant,
                    Engineer.user_id.is_(None),
                    func.lower(Engineer.display_name) == name.lower(),
                )
                .order_by(Engineer.is_active.desc(), Engineer.id.asc())
                .limit(2)
            )
        )
        .scalars()
        .all()
    )
    match = _adoptable_roster_row(candidates, user, name)
    if match is not None:
        match.user_id = user.id
        if not match.job_title and user.job_title:
            match.job_title = user.job_title
        if not match.department and user.department:
            match.department = user.department
        await db.flush()
        logger.info(
            "engineer_user_auto_linked engineer_id=%s user_id=%s via_display_name",
            match.id,
            user.id,
        )
        return match

    engineer = Engineer(
        user_id=user.id,
        display_name=name,
        job_title=user.job_title,
        department=user.department,
        is_active=True,
        tenant_id=effective_tenant,
    )
    db.add(engineer)
    await db.flush()
    logger.info(
        "engineer_user_auto_created engineer_id=%s user_id=%s",
        engineer.id,
        user.id,
    )
    return engineer


def ensure_engineer_for_user_sync(
    db: Session,
    user: User,
    *,
    tenant_id: Optional[int] = None,
) -> Engineer:
    """Sync Session variant (PAMS / scripts)."""
    effective_tenant = tenant_id if tenant_id is not None else user.tenant_id
    if effective_tenant is None:
        raise ValueError("tenant_id is required to ensure an engineer profile")

    existing = db.execute(select(Engineer).where(Engineer.user_id == user.id)).scalar_one_or_none()
    if existing is not None:
        return existing

    name = display_name_for_user(user)
    candidates = list(
        db.execute(
            select(Engineer)
            .where(
                Engineer.tenant_id == effective_tenant,
                Engineer.user_id.is_(None),
                func.lower(Engineer.display_name) == name.lower(),
            )
            .order_by(Engineer.is_active.desc(), Engineer.id.asc())
            .limit(2)
        )
        .scalars()
        .all()
    )
    match = _adoptable_roster_row(candidates, user, name)
    if match is not None:
        match.user_id = user.id
        db.flush()
        return match

    engineer = Engineer(
        user_id=user.id,
        display_name=name,
        job_title=user.job_title,
        department=user.department,
        is_active=True,
        tenant_id=effective_tenant,
    )
    db.add(engineer)
    db.flush()
    return engineer
