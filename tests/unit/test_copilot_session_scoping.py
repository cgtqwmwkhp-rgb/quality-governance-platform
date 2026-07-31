"""Copilot session ownership: cross-user and cross-tenant access must fail closed.

Refusals use not-found semantics (ValueError) so callers cannot distinguish missing
resources from resources owned by someone else.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings
from src.domain.models.ai_copilot import CopilotFeedback, CopilotMessage, CopilotSession
from src.domain.services.copilot_service import CopilotService

TENANT_A = 1
TENANT_B = 2
USER_OWNER = 10
USER_PEER = 11
USER_OTHER_TENANT = 20


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(CopilotSession.__table__.create)
        await conn.run_sync(CopilotMessage.__table__.create)
        await conn.run_sync(CopilotFeedback.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest.fixture
def copilot_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "app_env", "development")


async def _seed_owned_session(db: AsyncSession, *, tenant_id: int, user_id: int) -> CopilotSession:
    session = CopilotSession(tenant_id=tenant_id, user_id=user_id, is_active=True)
    db.add(session)
    await db.flush()
    return session


async def _seed_assistant_message(db: AsyncSession, session: CopilotSession) -> CopilotMessage:
    message = CopilotMessage(
        session_id=session.id,
        role="assistant",
        content="simulated reply",
    )
    db.add(message)
    await db.flush()
    return message


@pytest.mark.asyncio
async def test_get_session_refuses_cross_user_and_cross_tenant(session_factory):
    async with session_factory() as db:
        service = CopilotService(db)
        owned = await _seed_owned_session(db, tenant_id=TENANT_A, user_id=USER_OWNER)
        await db.commit()

        assert (
            await service.get_session(
                owned.id,
                user_id=USER_OWNER,
                tenant_id=TENANT_A,
            )
            is not None
        )
        assert (
            await service.get_session(
                owned.id,
                user_id=USER_PEER,
                tenant_id=TENANT_A,
            )
            is None
        )
        assert (
            await service.get_session(
                owned.id,
                user_id=USER_OTHER_TENANT,
                tenant_id=TENANT_B,
            )
            is None
        )


@pytest.mark.asyncio
async def test_get_active_session_is_tenant_scoped(session_factory):
    async with session_factory() as db:
        service = CopilotService(db)
        await _seed_owned_session(db, tenant_id=TENANT_A, user_id=USER_OWNER)
        await db.commit()

        assert await service.get_active_session(USER_OWNER, TENANT_A) is not None
        assert await service.get_active_session(USER_OWNER, TENANT_B) is None


@pytest.mark.asyncio
async def test_get_session_messages_refuses_without_ownership(session_factory):
    async with session_factory() as db:
        service = CopilotService(db)
        owned = await _seed_owned_session(db, tenant_id=TENANT_A, user_id=USER_OWNER)
        db.add(
            CopilotMessage(session_id=owned.id, role="user", content="hello"),
        )
        await db.commit()

        messages = await service.get_session_messages(
            owned.id,
            user_id=USER_OWNER,
            tenant_id=TENANT_A,
        )
        assert len(messages) == 1

        with pytest.raises(ValueError, match="not found"):
            await service.get_session_messages(
                owned.id,
                user_id=USER_PEER,
                tenant_id=TENANT_A,
            )

        with pytest.raises(ValueError, match="not found"):
            await service.get_session_messages(
                owned.id,
                user_id=USER_OTHER_TENANT,
                tenant_id=TENANT_B,
            )


@pytest.mark.asyncio
async def test_close_session_refuses_without_ownership(session_factory):
    async with session_factory() as db:
        service = CopilotService(db)
        owned = await _seed_owned_session(db, tenant_id=TENANT_A, user_id=USER_OWNER)
        await db.commit()

        with pytest.raises(ValueError, match="not found"):
            await service.close_session(
                owned.id,
                user_id=USER_PEER,
                tenant_id=TENANT_A,
            )

        closed = await service.close_session(
            owned.id,
            user_id=USER_OWNER,
            tenant_id=TENANT_A,
        )
        assert closed.is_active is False


@pytest.mark.asyncio
async def test_send_message_refuses_without_ownership(session_factory, copilot_enabled):
    async with session_factory() as db:
        service = CopilotService(db)
        owned = await _seed_owned_session(db, tenant_id=TENANT_A, user_id=USER_OWNER)
        await db.commit()

        with pytest.raises(ValueError, match="not found"):
            await service.send_message(
                owned.id,
                "cross-user attempt",
                user_id=USER_PEER,
                tenant_id=TENANT_A,
            )

        with pytest.raises(ValueError, match="not found"):
            await service.send_message(
                owned.id,
                "cross-tenant attempt",
                user_id=USER_OTHER_TENANT,
                tenant_id=TENANT_B,
            )

        reply = await service.send_message(
            owned.id,
            "owned message",
            user_id=USER_OWNER,
            tenant_id=TENANT_A,
        )
        assert reply.role == "assistant"


@pytest.mark.asyncio
async def test_submit_feedback_refuses_without_session_ownership(session_factory):
    async with session_factory() as db:
        service = CopilotService(db)
        owned = await _seed_owned_session(db, tenant_id=TENANT_A, user_id=USER_OWNER)
        assistant = await _seed_assistant_message(db, owned)
        await db.commit()

        feedback = await service.submit_feedback(
            message_id=assistant.id,
            user_id=USER_OWNER,
            tenant_id=TENANT_A,
            rating=5,
            feedback_type="helpful",
        )
        assert feedback.id is not None

        with pytest.raises(ValueError, match="not found"):
            await service.submit_feedback(
                message_id=assistant.id,
                user_id=USER_PEER,
                tenant_id=TENANT_A,
                rating=1,
                feedback_type="inaccurate",
            )

        with pytest.raises(ValueError, match="not found"):
            await service.submit_feedback(
                message_id=assistant.id,
                user_id=USER_OTHER_TENANT,
                tenant_id=TENANT_B,
                rating=1,
                feedback_type="inaccurate",
            )
