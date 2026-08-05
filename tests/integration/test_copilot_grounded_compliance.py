"""The compliance obligation intent against a real database.

Every assertion is scoped to rows this test created, in tenants this test created,
because ``conftest`` only drops the schema on SQLite — a PostgreSQL run inherits
every row earlier tests left behind, so a global count would pass locally and fail
in CI.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from src.core.config import settings
from src.domain.models.ai_copilot import CopilotSession
from src.domain.models.compliance_schedule import ComplianceRequirement, ComplianceScheduleAnchor
from src.domain.models.user import Role, User
from src.domain.services.compliance_schedule_kill_switch import reset_compliance_schedule_kill_switch_cache
from src.domain.services.copilot_grounding import CopilotGroundingService
from src.domain.services.copilot_kill_switch import reset_copilot_kill_switch_cache
from src.domain.services.copilot_service import CopilotService

OVERDUE_QUESTION = "How many overdue compliance obligations do we have?"
DUE_SOON_QUESTION = "Which compliance obligations are due soon?"


@pytest.fixture(autouse=True)
def copilot_and_module_on(monkeypatch):
    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "ai_copilot_inference_enabled", True)
    monkeypatch.setattr(settings, "compliance_schedule_enabled", True)
    reset_compliance_schedule_kill_switch_cache()
    reset_copilot_kill_switch_cache()
    yield
    reset_compliance_schedule_kill_switch_cache()
    reset_copilot_kill_switch_cache()


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Deterministic phrasing: the fact formatter, never a credentialed provider."""
    monkeypatch.setattr(CopilotGroundingService, "_provider_available", staticmethod(lambda: False))


async def _make_tenant(session, label: str) -> int:
    from tests.factories import TenantFactory

    suffix = uuid.uuid4().hex[:10]
    tenant = TenantFactory.build(
        name=f"Copilot Compliance {label} {suffix}",
        slug=f"copilot-compliance-{label}-{suffix}",
        admin_email=f"admin-{suffix}@example.com",
        is_active=True,
    )
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)
    return int(tenant.id)


async def _make_user(session, *, tenant_id: int, permissions: list[str] | None) -> int:
    from src.core.security import get_password_hash

    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"caller-{suffix}@example.com",
        hashed_password=get_password_hash("testpassword123"),
        first_name="Cal",
        last_name="Ler",
        is_active=True,
        is_superuser=False,
        tenant_id=tenant_id,
    )
    if permissions is not None:
        # Role.name is globally unique, so it must not be a fixed literal.
        user.roles = [
            Role(
                name=f"copilot-compliance-{suffix}",
                tenant_id=tenant_id,
                permissions=json.dumps(permissions),
            )
        ]
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return int(user.id)


async def _add_requirement(
    session,
    *,
    tenant_id: int,
    ref: str,
    next_due_date: date,
    statutory: bool = False,
    is_active: bool = True,
    deleted_at: datetime | None = None,
) -> int:
    requirement = ComplianceRequirement(
        tenant_id=tenant_id,
        reference_number=ref,
        title=f"Obligation {ref}",
        taxonomy_id="HS-01",
        frequency_months=12,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=statutory,
        next_due_date=next_due_date,
        is_active=is_active,
        deleted_at=deleted_at,
    )
    session.add(requirement)
    await session.commit()
    await session.refresh(requirement)
    return int(requirement.id)


@pytest.fixture
async def register(test_session):
    """One tenant with a known register, plus a neighbour tenant that must not leak.

    Tenant A holds two overdue obligations (one statutory), one due today, one due
    inside the horizon, one far future, and two that are overdue but not live — a
    soft-deleted row and a deactivated row.
    """
    today = datetime.now(timezone.utc).date()
    tenant_a = await _make_tenant(test_session, "a")
    tenant_b = await _make_tenant(test_session, "b")

    await _add_requirement(
        test_session, tenant_id=tenant_a, ref="CSR-2026-0001", next_due_date=today - timedelta(days=1), statutory=True
    )
    await _add_requirement(
        test_session, tenant_id=tenant_a, ref="CSR-2026-0002", next_due_date=today - timedelta(days=40)
    )
    await _add_requirement(test_session, tenant_id=tenant_a, ref="CSR-2026-0003", next_due_date=today)
    await _add_requirement(
        test_session, tenant_id=tenant_a, ref="CSR-2026-0004", next_due_date=today + timedelta(days=10)
    )
    await _add_requirement(
        test_session, tenant_id=tenant_a, ref="CSR-2026-0005", next_due_date=today + timedelta(days=200)
    )
    await _add_requirement(
        test_session,
        tenant_id=tenant_a,
        ref="CSR-2026-0006",
        next_due_date=today - timedelta(days=5),
        deleted_at=datetime.now(timezone.utc),
    )
    await _add_requirement(
        test_session,
        tenant_id=tenant_a,
        ref="CSR-2026-0007",
        next_due_date=today - timedelta(days=5),
        is_active=False,
    )
    # The neighbour: overdue, statutory, and none of tenant A's business.
    await _add_requirement(
        test_session, tenant_id=tenant_b, ref="CSR-2026-0900", next_due_date=today - timedelta(days=3), statutory=True
    )

    reader = await _make_user(test_session, tenant_id=tenant_a, permissions=["compliance_schedule:read"])
    non_reader = await _make_user(test_session, tenant_id=tenant_a, permissions=["incident:read", "complaint:read"])
    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "reader": reader,
        "non_reader": non_reader,
    }


# --------------------------------------------------------------------------- counts


@pytest.mark.asyncio
async def test_overdue_count_excludes_deleted_inactive_today_and_other_tenants(test_session, register):
    service = CopilotGroundingService(test_session)

    facts = await service.gather_facts("compliance_overdue", tenant_id=register["tenant_a"])

    assert facts.count == 2, "expected only the two live overdue rows this test created"
    assert facts.extras["statutory_overdue"] == 1
    assert [r.reference_number for r in facts.refs] == ["CSR-2026-0002", "CSR-2026-0001"]
    assert "CSR-2026-0900" not in facts.allowed_refs(), "another tenant's obligation leaked"
    assert "CSR-2026-0006" not in facts.allowed_refs(), "a soft-deleted obligation was counted"
    assert "CSR-2026-0007" not in facts.allowed_refs(), "a deactivated obligation was counted"


@pytest.mark.asyncio
async def test_due_soon_count_includes_today_and_stops_at_the_horizon(test_session, register):
    service = CopilotGroundingService(test_session)

    facts = await service.gather_facts("compliance_due_soon", tenant_id=register["tenant_a"])

    assert facts.count == 2
    assert {r.reference_number for r in facts.refs} == {"CSR-2026-0003", "CSR-2026-0004"}
    assert facts.extras["horizon_days"] == 30


@pytest.mark.asyncio
async def test_a_tenant_with_no_obligations_is_told_zero(test_session):
    empty_tenant = await _make_tenant(test_session, "empty")
    reader = await _make_user(test_session, tenant_id=empty_tenant, permissions=["compliance_schedule:read"])
    service = CopilotGroundingService(test_session)

    outcome = await service.try_answer(OVERDUE_QUESTION, tenant_id=empty_tenant, user_id=reader)

    assert outcome.kind == "answered"
    assert outcome.content is not None
    assert "Overdue compliance obligation count: 0." in outcome.content
    assert "No matching records in this organisation." in outcome.content


@pytest.mark.asyncio
async def test_everything_overdue_is_reported_as_everything(test_session):
    tenant_id = await _make_tenant(test_session, "allbad")
    reader = await _make_user(test_session, tenant_id=tenant_id, permissions=["compliance_schedule:read"])
    today = datetime.now(timezone.utc).date()
    for index in range(3):
        await _add_requirement(
            test_session,
            tenant_id=tenant_id,
            ref=f"CSR-2026-01{index:02d}",
            next_due_date=today - timedelta(days=index + 1),
            statutory=True,
        )
    service = CopilotGroundingService(test_session)

    facts = await service.gather_facts("compliance_overdue", tenant_id=tenant_id)
    due_soon = await service.gather_facts("compliance_due_soon", tenant_id=tenant_id)

    assert facts.count == 3
    assert facts.extras["statutory_overdue"] == 3
    assert due_soon.count == 0
    outcome = await service.try_answer(OVERDUE_QUESTION, tenant_id=tenant_id, user_id=reader)
    assert outcome.kind == "answered"
    assert outcome.content is not None
    assert "Overdue compliance obligation count: 3." in outcome.content


# --------------------------------------------------------------------------- gates


@pytest.mark.asyncio
async def test_a_caller_without_the_permission_is_told_nothing(test_session, register):
    service = CopilotGroundingService(test_session)

    outcome = await service.try_answer(
        OVERDUE_QUESTION,
        tenant_id=register["tenant_a"],
        user_id=register["non_reader"],
    )

    assert outcome.kind == "ungrounded"
    assert outcome.content is None


@pytest.mark.asyncio
async def test_a_reader_of_another_tenant_is_told_nothing(test_session, register):
    """Tenant A's reader asking about tenant B resolves to nobody in tenant B."""
    service = CopilotGroundingService(test_session)

    outcome = await service.try_answer(
        OVERDUE_QUESTION,
        tenant_id=register["tenant_b"],
        user_id=register["reader"],
    )

    assert outcome.kind == "ungrounded"


@pytest.mark.asyncio
async def test_a_deactivated_reader_is_told_nothing(test_session, register):
    disabled = await _make_user(test_session, tenant_id=register["tenant_a"], permissions=["compliance_schedule:read"])
    user = await test_session.get(User, disabled)
    user.is_active = False
    await test_session.commit()
    service = CopilotGroundingService(test_session)

    outcome = await service.try_answer(OVERDUE_QUESTION, tenant_id=register["tenant_a"], user_id=disabled)

    assert outcome.kind == "ungrounded"


@pytest.mark.asyncio
async def test_module_switched_off_for_the_tenant_answers_nothing(test_session, register, monkeypatch):
    monkeypatch.setattr(settings, "compliance_schedule_enabled", False)
    reset_compliance_schedule_kill_switch_cache()
    service = CopilotGroundingService(test_session)

    outcome = await service.try_answer(
        OVERDUE_QUESTION,
        tenant_id=register["tenant_a"],
        user_id=register["reader"],
    )

    assert outcome.kind == "ungrounded"


# --------------------------------------------------------------------------- end to end


async def _send(test_session, *, tenant_id: int, user_id: int, question: str):
    session_row = CopilotSession(tenant_id=tenant_id, user_id=user_id, context_data={})
    test_session.add(session_row)
    await test_session.commit()
    await test_session.refresh(session_row)

    service = CopilotService(test_session)
    return await service.send_message(
        session_id=session_row.id,
        content=question,
        user_id=user_id,
        tenant_id=tenant_id,
    )


@pytest.mark.asyncio
async def test_send_message_serves_the_real_count_to_a_reader(test_session, register):
    message = await _send(
        test_session,
        tenant_id=register["tenant_a"],
        user_id=register["reader"],
        question=OVERDUE_QUESTION,
    )

    assert message.model_used == "grounded-facts"
    assert "Overdue compliance obligation count: 2." in message.content
    assert "CSR-2026-0001" in message.content
    assert "CSR-2026-0900" not in message.content


@pytest.mark.asyncio
async def test_send_message_refuses_a_caller_without_the_permission(test_session, register):
    message = await _send(
        test_session,
        tenant_id=register["tenant_a"],
        user_id=register["non_reader"],
        question=OVERDUE_QUESTION,
    )

    assert message.model_used == "simulated-keyword-match"
    assert "cannot answer from live organisation data" in message.content.lower()
    assert "CSR-" not in message.content
    assert "Overdue compliance obligation count" not in message.content


@pytest.mark.asyncio
async def test_the_refusal_does_not_reveal_which_gate_closed(test_session, register, monkeypatch):
    """No permission and module-off must be indistinguishable to the caller.

    If they differed, a user without the grant could tell that the module is live
    for their organisation, which is the disclosure the permission exists to stop.
    """
    without_permission = await _send(
        test_session,
        tenant_id=register["tenant_a"],
        user_id=register["non_reader"],
        question=OVERDUE_QUESTION,
    )

    monkeypatch.setattr(settings, "compliance_schedule_enabled", False)
    reset_compliance_schedule_kill_switch_cache()
    module_off = await _send(
        test_session,
        tenant_id=register["tenant_a"],
        user_id=register["reader"],
        question=OVERDUE_QUESTION,
    )

    assert without_permission.content == module_off.content
    assert without_permission.model_used == module_off.model_used


@pytest.mark.asyncio
async def test_send_message_due_soon_answers_a_reader(test_session, register):
    message = await _send(
        test_session,
        tenant_id=register["tenant_a"],
        user_id=register["reader"],
        question=DUE_SOON_QUESTION,
    )

    assert message.model_used == "grounded-facts"
    assert "Compliance obligations due soon: 2." in message.content
