"""A run cannot answer another tenant's question, end to end through the app.

The question was fetched by bare primary key, so nothing stopped a caller
attaching a response to a question from another organisation's private
template — after which that question's text is rendered inside the caller's own
run. Unlike the run filter, this hole is reachable in the test harness, because
it needs no NULL ``tenant_id`` to exercise.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditQuestion, AuditResponse, AuditRun, AuditSection, AuditStatus, AuditTemplate
from tests.conftest import generate_test_reference

CALLER_TENANT_ID = 1
FOREIGN_QUESTION_TEXT = "Commercially sensitive question from another organisation"


async def _template_with_question(
    session: AsyncSession,
    *,
    tenant_id: int,
    question_text: str,
) -> tuple[AuditTemplate, AuditQuestion]:
    template = AuditTemplate(
        name=f"Question ownership {uuid.uuid4().hex[:8]}",
        category="Safety",
        audit_type="inspection",
        auto_create_findings=False,
        is_published=True,
        is_active=True,
        tenant_id=tenant_id,
        created_by_id=1,
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
        question_text=question_text,
        question_type="yes_no",
        positive_answer="yes",
        sort_order=1,
    )
    session.add(question)
    await session.flush()
    return template, question


async def _foreign_tenant_id(session: AsyncSession) -> int:
    from tests.factories import TenantFactory

    tenant = TenantFactory.build(
        name=f"Other Org {uuid.uuid4().hex[:6]}",
        slug=f"other-org-{uuid.uuid4().hex[:8]}",
        admin_email=f"admin-{uuid.uuid4().hex[:8]}@other.example.com",
        is_active=True,
    )
    session.add(tenant)
    await session.flush()
    assert tenant.id != CALLER_TENANT_ID
    return tenant.id


@pytest.mark.asyncio
async def test_response_cannot_answer_a_question_from_another_tenants_template(
    client: AsyncClient,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    foreign_tenant_id = await _foreign_tenant_id(test_session)
    _, foreign_question = await _template_with_question(
        test_session,
        tenant_id=foreign_tenant_id,
        question_text=FOREIGN_QUESTION_TEXT,
    )
    own_template, own_question = await _template_with_question(
        test_session,
        tenant_id=CALLER_TENANT_ID,
        question_text="Are the guards fitted?",
    )
    run = AuditRun(
        template_id=own_template.id,
        title="Question ownership run",
        status=AuditStatus.IN_PROGRESS,
        tenant_id=CALLER_TENANT_ID,
        assigned_to_id=1,
        created_by_id=1,
        reference_number=generate_test_reference("AUD"),
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)
    run_id = run.id

    refused = await client.post(
        f"/api/v1/audits/runs/{run_id}/responses",
        headers=auth_headers,
        json={"question_id": foreign_question.id, "response_value": "yes"},
    )

    assert refused.status_code == 404, refused.text
    assert FOREIGN_QUESTION_TEXT not in refused.text
    rows = (await test_session.execute(select(AuditResponse).where(AuditResponse.run_id == run_id))).scalars().all()
    assert rows == []

    # The run still works for its own questions, so the guard is not a blanket
    # refusal that would pass for the wrong reason.
    accepted = await client.post(
        f"/api/v1/audits/runs/{run_id}/responses",
        headers=auth_headers,
        json={"question_id": own_question.id, "response_value": "yes"},
    )
    assert accepted.status_code == 201, accepted.text
