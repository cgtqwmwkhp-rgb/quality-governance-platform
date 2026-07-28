"""End-to-end tenancy of `audit_responses`, through the ASGI app and a database.

The companion unit tests (``tests/unit/test_audit_response_tenancy.py``) pin the
declaration and the provenance of the stamped value. These pin that a real
request actually persists it, and that a run belonging to another tenant is not
writable at all.

Worth stating what the harness can and cannot show. On SQLite the schema is
built from the models, so ``audit_responses.tenant_id`` is NOT NULL there and an
unstamped write would fail on the constraint rather than on the assertion. On
CI's PostgreSQL the schema comes from Alembic and the column is still nullable
(no migration lands in this step), so the same assertion is the only thing
standing between a NULL and a green run. Neither harness can hold a run with a
NULL ``tenant_id``, which is why that case is asserted at the unit level.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import (
    AuditQuestion,
    AuditResponse,
    AuditRun,
    AuditSection,
    AuditStatus,
    AuditTemplate,
)
from tests.conftest import generate_test_reference

CALLER_TENANT_ID = 1


async def _seed_run(
    session: AsyncSession,
    *,
    tenant_id: int,
    created_by_id: int = 1,
) -> tuple[AuditRun, AuditQuestion]:
    """Create a published template with one question, and an in-progress run."""
    template = AuditTemplate(
        name=f"Response tenancy {uuid.uuid4().hex[:8]}",
        category="Safety",
        audit_type="inspection",
        auto_create_findings=False,
        is_published=True,
        is_active=True,
        tenant_id=tenant_id,
        created_by_id=created_by_id,
        version=1,
        reference_number=generate_test_reference("TPL"),
    )
    session.add(template)
    await session.flush()

    section = AuditSection(template_id=template.id, title="Guarding", sort_order=1)
    session.add(section)
    await session.flush()

    question = AuditQuestion(
        template_id=template.id,
        section_id=section.id,
        question_text="Are the guards fitted?",
        question_type="yes_no",
        positive_answer="yes",
        sort_order=1,
    )
    session.add(question)
    await session.flush()

    run = AuditRun(
        template_id=template.id,
        title="Response tenancy run",
        status=AuditStatus.IN_PROGRESS,
        tenant_id=tenant_id,
        assigned_to_id=created_by_id,
        created_by_id=created_by_id,
        reference_number=generate_test_reference("AUD"),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    await session.refresh(question)
    return run, question


async def _other_tenant_id(session: AsyncSession) -> int:
    from tests.factories import TenantFactory

    tenant = TenantFactory.build(
        name=f"Other Org {uuid.uuid4().hex[:6]}",
        slug=f"other-org-{uuid.uuid4().hex[:8]}",
        admin_email=f"admin-{uuid.uuid4().hex[:8]}@other.example.com",
        is_active=True,
    )
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)
    assert tenant.id != CALLER_TENANT_ID
    return tenant.id


@pytest.mark.asyncio
async def test_response_written_through_the_api_is_attributed_to_the_runs_tenant(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """The defect this closes: 315 production rows, every one unattributed."""
    run, question = await _seed_run(test_session, tenant_id=CALLER_TENANT_ID)
    run_tenant_id = run.tenant_id

    created = await client.post(
        f"/api/v1/audits/runs/{run.id}/responses",
        headers=auth_headers,
        json={"question_id": question.id, "response_value": "yes"},
    )
    assert created.status_code == 201, created.text

    stored = (
        await test_session.execute(select(AuditResponse).where(AuditResponse.id == created.json()["id"]))
    ).scalar_one()
    assert stored.tenant_id is not None
    assert stored.tenant_id == run_tenant_id == CALLER_TENANT_ID


@pytest.mark.asyncio
async def test_response_cannot_be_written_into_another_tenants_run(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """Isolation is asserted at the application layer because nothing else does it.

    The application connects to production as a role with ``rolbypassrls``, so
    the FORCE ROW LEVEL SECURITY on ``audit_runs`` is bypassed and cannot be
    relied on as a second line of defence here.

    Scope, stated so this is not mistaken for proof of the filter change: this
    passes both before and after it. The branch that was removed matched runs
    with a NULL ``tenant_id``, and neither harness can hold such a row — see the
    module docstring. What this covers is the other direction: that a run
    belonging to a *named* other tenant stays unwritable.
    """
    other_tenant_id = await _other_tenant_id(test_session)
    run, question = await _seed_run(test_session, tenant_id=other_tenant_id)

    refused = await client.post(
        f"/api/v1/audits/runs/{run.id}/responses",
        headers=auth_headers,
        json={"question_id": question.id, "response_value": "yes"},
    )

    assert refused.status_code == 404, refused.text
    rows = (await test_session.execute(select(AuditResponse).where(AuditResponse.run_id == run.id))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_another_tenants_run_is_not_writable_even_once_it_is_started(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """The refusal is the tenant filter, not the run's status.

    A 404 on a SCHEDULED run would also be produced by the "not writable"
    branch, so the run above is IN_PROGRESS and this one is SCHEDULED: both
    refuse, and neither is auto-started as a side effect.
    """
    other_tenant_id = await _other_tenant_id(test_session)
    run, question = await _seed_run(test_session, tenant_id=other_tenant_id)
    run.status = AuditStatus.SCHEDULED
    await test_session.commit()

    refused = await client.post(
        f"/api/v1/audits/runs/{run.id}/responses",
        headers=auth_headers,
        json={"question_id": question.id, "response_value": "yes"},
    )

    assert refused.status_code == 404, refused.text
    await test_session.refresh(run)
    assert run.status == AuditStatus.SCHEDULED
    assert run.started_at is None
