"""The dedupe index must refuse a duplicate through the ORM, on the real dialect.

The unit test alongside this one compiles the index and exercises it against
sqlite3 directly, which proves the DDL is right. It cannot prove the index is
actually present in a database the application built, or that a second insert
through a SQLAlchemy session raises rather than quietly succeeding. That is what
the Wave 2 sweep depends on, so it is asserted here against whatever dialect the
suite is running on -- SQLite locally, PostgreSQL in CI.

Rows are removed explicitly in a finally rather than left to the harness. The
integration conftest only calls ``drop_all`` on SQLite, so on PostgreSQL anything
committed here survives into every later test in the run; a uniquely-constrained
table is a particularly unkind place to leave residue.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from src.domain.models.notification import Notification, NotificationPriority, NotificationType

ENTITY_TYPE = "compliance_requirement"


def _notification(user_id: int, dedupe_key: str | None, entity_type: str = ENTITY_TYPE) -> Notification:
    return Notification(
        user_id=user_id,
        type=NotificationType.COMPLIANCE_ALERT,
        priority=NotificationPriority.HIGH,
        title="Fire risk assessment due",
        message="Due in 7 days.",
        entity_type=entity_type,
        entity_id="12",
        extra_data={"dedupe_key": dedupe_key} if dedupe_key is not None else None,
        is_read=False,
    )


async def test_duplicate_dedupe_key_is_refused_by_the_database(test_session, test_user) -> None:
    user_id = test_user.id
    key = f"12:2026-09-01:due_7:{uuid.uuid4().hex[:8]}"
    try:
        test_session.add(_notification(user_id, key))
        await test_session.commit()

        test_session.add(_notification(user_id, key))
        with pytest.raises(IntegrityError):
            await test_session.commit()
        await test_session.rollback()

        stored = (
            (await test_session.execute(select(Notification).where(Notification.user_id == user_id))).scalars().all()
        )
        assert len(stored) == 1, "the second insert was accepted; the index is not enforcing"
    finally:
        await test_session.rollback()
        await test_session.execute(delete(Notification).where(Notification.user_id == user_id))
        await test_session.commit()


async def test_a_different_band_for_the_same_occurrence_is_allowed(test_session, test_user) -> None:
    """A requirement that goes overdue after a due_7 warning owes a second notice."""
    user_id = test_user.id
    suffix = uuid.uuid4().hex[:8]
    try:
        test_session.add(_notification(user_id, f"12:2026-09-01:due_7:{suffix}"))
        test_session.add(_notification(user_id, f"12:2026-09-01:overdue:{suffix}"))
        await test_session.commit()

        stored = (
            (await test_session.execute(select(Notification).where(Notification.user_id == user_id))).scalars().all()
        )
        assert len(stored) == 2
    finally:
        await test_session.rollback()
        await test_session.execute(delete(Notification).where(Notification.user_id == user_id))
        await test_session.commit()


async def test_ordinary_notifications_are_untouched_by_the_index(test_session, test_user) -> None:
    """The predicate is the whole reason this index is safe on a shared table.

    Two notifications with no ``dedupe_key`` both fold to the empty string under the
    COALESCE. Without the ``entity_type`` predicate the second would be refused, and
    every feature that notifies a user twice would break.
    """
    user_id = test_user.id
    try:
        test_session.add(_notification(user_id, None, entity_type="incident"))
        test_session.add(_notification(user_id, None, entity_type="action"))
        await test_session.commit()

        stored = (
            (await test_session.execute(select(Notification).where(Notification.user_id == user_id))).scalars().all()
        )
        assert len(stored) == 2, "the index is constraining rows outside the compliance schedule"
    finally:
        await test_session.rollback()
        await test_session.execute(delete(Notification).where(Notification.user_id == user_id))
        await test_session.commit()
