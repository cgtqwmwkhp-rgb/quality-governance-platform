"""Unit tests for AuditChallengeService session lifecycle, decide, and apply.

Uses an isolated in-memory SQLite schema containing only the three
Check & Challenge tables — SQLite does not enforce FK targets by default, so
tenants/users/audit_templates rows are not required for these CRUD paths.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.models.audit_challenge import (
    AuditChallengeProposal,
    AuditChallengeSession,
    AuditChallengeTurn,
)
from src.domain.services.audit_challenge_service import AuditChallengeService

TENANT_ID = 1


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AuditChallengeSession.__table__.create)
        await conn.run_sync(AuditChallengeTurn.__table__.create)
        await conn.run_sync(AuditChallengeProposal.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


def _sections() -> list[dict]:
    return [
        {
            "id": "s1",
            "title": "Section 1",
            "questions": [
                {"id": "q1", "text": "Is the guard fitted correctly?", "type": "yes_no", "weight": 1},
                {"id": "q2", "text": "OK?", "type": "yes_no", "weight": 1},
            ],
        }
    ]


@pytest.mark.asyncio
async def test_create_session_persists_snapshot_and_user_turn(session_factory):
    async with session_factory() as db:
        service = AuditChallengeService(db)
        session = await service.create_session(
            tenant_id=TENANT_ID,
            user_id=7,
            sections=_sections(),
            chip_id="field_assessor",
        )
        await db.commit()

        assert session.id is not None
        assert session.status.value == "queued"
        assert session.template_snapshot_json["sections"][0]["id"] == "s1"

        turns = await service.list_turns(session.id, TENANT_ID)
        assert len(turns) == 1
        assert turns[0].role.value == "user"
        assert turns[0].chip_id == "field_assessor"


@pytest.mark.asyncio
async def test_get_session_scoped_to_tenant(session_factory):
    async with session_factory() as db:
        service = AuditChallengeService(db)
        session = await service.create_session(tenant_id=TENANT_ID, user_id=None, sections=_sections())
        await db.commit()

        assert await service.get_session(session.id, TENANT_ID) is not None
        assert await service.get_session(session.id, tenant_id=999) is None


@pytest.mark.asyncio
async def test_decide_proposal_accept_reject_and_edit(session_factory):
    async with session_factory() as db:
        service = AuditChallengeService(db)
        session = await service.create_session(tenant_id=TENANT_ID, user_id=None, sections=_sections())
        await db.flush()

        proposal = AuditChallengeProposal(
            session_id=session.id,
            tenant_id=TENANT_ID,
            proposal_key="p-1",
            target_path="sections[s1].questions[q1]",
            before_json={"id": "q1", "text": "Old"},
            after_json={"id": "q1", "text": "New"},
        )
        db.add(proposal)
        await db.commit()

        accepted = await service.decide_proposal(
            session_id=session.id, proposal_id=proposal.id, tenant_id=TENANT_ID, decision="accept"
        )
        assert accepted.decision.value == "accepted"

        edited = await service.decide_proposal(
            session_id=session.id,
            proposal_id=proposal.id,
            tenant_id=TENANT_ID,
            decision="edit",
            edited_after={"id": "q1", "text": "Edited text"},
        )
        assert edited.decision.value == "edited"
        assert edited.edited_after_json["text"] == "Edited text"

        with pytest.raises(ValueError, match="INVALID_DECISION"):
            await service.decide_proposal(
                session_id=session.id, proposal_id=proposal.id, tenant_id=TENANT_ID, decision="bogus"
            )

        with pytest.raises(ValueError, match="EDITED_AFTER_REQUIRED"):
            await service.decide_proposal(
                session_id=session.id, proposal_id=proposal.id, tenant_id=TENANT_ID, decision="edit"
            )


@pytest.mark.asyncio
async def test_apply_accepted_merges_edited_and_accepted_only(session_factory):
    async with session_factory() as db:
        service = AuditChallengeService(db)
        session = await service.create_session(tenant_id=TENANT_ID, user_id=None, sections=_sections())
        await db.flush()

        accepted_proposal = AuditChallengeProposal(
            session_id=session.id,
            tenant_id=TENANT_ID,
            proposal_key="p-accept",
            target_path="sections[s1].questions[q1]",
            after_json={"id": "q1", "text": "Accepted text"},
            decision="accepted",
        )
        rejected_proposal = AuditChallengeProposal(
            session_id=session.id,
            tenant_id=TENANT_ID,
            proposal_key="p-reject",
            target_path="sections[s1].questions[q2]",
            after_json={"id": "q2", "text": "Should not apply"},
            decision="rejected",
        )
        db.add_all([accepted_proposal, rejected_proposal])
        await db.commit()

        result = await service.apply_accepted(session_id=session.id, tenant_id=TENANT_ID)
        assert result["applied_count"] == 1
        merged_questions = {q["id"]: q for sec in result["sections"] for q in sec["questions"]}
        assert merged_questions["q1"]["text"] == "Accepted text"
        assert merged_questions["q2"]["text"] == "OK?"


@pytest.mark.asyncio
async def test_serialize_session_shape(session_factory):
    async with session_factory() as db:
        service = AuditChallengeService(db)
        session = await service.create_session(
            tenant_id=TENANT_ID, user_id=3, sections=_sections(), user_message="tighten this up"
        )
        await db.commit()

        payload = await service.serialize_session(session)
        assert payload["id"] == session.id
        assert payload["status"] == "queued"
        assert payload["chips"]
        assert len(payload["turns"]) == 1
        assert payload["proposals"] == []


@pytest.mark.asyncio
async def test_enqueue_follow_up_resets_status_for_next_cycle(session_factory):
    async with session_factory() as db:
        service = AuditChallengeService(db)
        session = await service.create_session(tenant_id=TENANT_ID, user_id=None, sections=_sections())
        session.status = "succeeded"
        await db.commit()

        updated = await service.enqueue_follow_up(
            session_id=session.id, tenant_id=TENANT_ID, user_id=None, message="what about ISO?"
        )
        assert updated.status.value == "queued"
        assert updated.user_message == "what about ISO?"

        with pytest.raises(ValueError, match="SESSION_NOT_FOUND"):
            await service.enqueue_follow_up(session_id=999999, tenant_id=TENANT_ID, user_id=None, message="x")
