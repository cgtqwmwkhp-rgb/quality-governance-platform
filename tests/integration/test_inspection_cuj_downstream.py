"""Live-database proof for the inspection finding → CAPA → risk journey."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import (
    AuditFinding,
    AuditQuestion,
    AuditResponse,
    AuditRun,
    AuditSection,
    AuditStatus,
    AuditTemplate,
    audit_finding_risks,
)
from src.domain.models.capa import CAPAAction, CAPASource
from src.domain.models.risk_register import EnterpriseRisk
from src.infrastructure.database import engine
from tests.conftest import generate_test_reference

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="Inspection risk materialization uses PostgreSQL JSONB containment",
)


async def _inspection_run(
    session: AsyncSession,
    *,
    status: AuditStatus = AuditStatus.IN_PROGRESS,
    with_failed_response: bool = False,
) -> tuple[AuditRun, AuditQuestion | None]:
    template = AuditTemplate(
        name="CUJ downstream inspection",
        category="Safety",
        audit_type="inspection",
        auto_create_findings=True,
        is_published=True,
        tenant_id=1,
        created_by_id=1,
        reference_number=generate_test_reference("TPL"),
    )
    session.add(template)
    await session.flush()

    question = None
    if with_failed_response:
        section = AuditSection(
            template_id=template.id,
            title="PPE controls",
            sort_order=1,
        )
        session.add(section)
        await session.flush()
        question = AuditQuestion(
            template_id=template.id,
            section_id=section.id,
            question_text="Are operators wearing the required PPE?",
            question_type="yes_no",
            positive_answer="yes",
            risk_weight=4,
            failure_triggers_action=True,
            sort_order=1,
        )
        session.add(question)
        await session.flush()

    run = AuditRun(
        template_id=template.id,
        title="CUJ warehouse inspection",
        location="Warehouse A",
        status=status,
        tenant_id=1,
        assigned_to_id=1,
        created_by_id=1,
        reference_number=generate_test_reference("AUD"),
    )
    session.add(run)
    await session.flush()

    if question is not None:
        session.add(
            AuditResponse(
                run_id=run.id,
                question_id=question.id,
                response_value="no",
                notes="Operator observed without gloves",
            )
        )

    await session.commit()
    await session.refresh(run)
    return run, question


async def _action_for_finding(session: AsyncSession, finding_id: int) -> CAPAAction | None:
    result = await session.execute(
        select(CAPAAction).where(
            CAPAAction.tenant_id == 1,
            CAPAAction.source_type == CAPASource.AUDIT_FINDING,
            CAPAAction.source_id == finding_id,
        )
    )
    return result.scalar_one_or_none()


async def _risks_for_finding(session: AsyncSession, finding_reference: str) -> list[EnterpriseRisk]:
    result = await session.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.tenant_id == 1,
            EnterpriseRisk.source == "audit_finding",
        )
    )
    return [risk for risk in result.scalars().all() if finding_reference in (risk.linked_audits or [])]


async def _junction_risk_ids(session: AsyncSession, finding_id: int) -> list[int]:
    result = await session.execute(
        select(audit_finding_risks.c.risk_id).where(
            audit_finding_risks.c.audit_finding_id == finding_id,
        )
    )
    return list(result.scalars().all())


async def test_create_finding_positive_gate_and_explicit_flag_risk(
    client,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """HTTP writes materialize CAPA/risk, while positive findings require an explicit flag."""
    run, _ = await _inspection_run(test_session)
    run_id = run.id

    issue_response = await client.post(
        f"/api/v1/audits/runs/{run_id}/findings",
        headers=auth_headers,
        json={
            "title": "Missing PPE at gate",
            "description": "Operator observed without gloves",
            "severity": "high",
            "finding_type": "nonconformity",
            "corrective_action_required": True,
        },
    )
    assert issue_response.status_code == 201, issue_response.text
    issue = issue_response.json()

    test_session.expire_all()
    action = await _action_for_finding(test_session, issue["id"])
    risks = await _risks_for_finding(test_session, issue["reference_number"])
    assert action is not None
    assert action.title == "Action plan: Missing PPE at gate"
    assert len(risks) == 1
    assert action.reference_number in (risks[0].linked_actions or [])
    assert issue["risk_ids"] == [risks[0].id]
    assert await _junction_risk_ids(test_session, issue["id"]) == [risks[0].id]

    positive_response = await client.post(
        f"/api/v1/audits/runs/{run_id}/findings",
        headers=auth_headers,
        json={
            "title": "Strong pre-start briefing",
            "description": "The team demonstrated positive practice",
            "severity": "critical",
            "finding_type": "positive_practice",
            "corrective_action_required": False,
        },
    )
    assert positive_response.status_code == 201, positive_response.text
    positive = positive_response.json()

    test_session.expire_all()
    assert await _action_for_finding(test_session, positive["id"]) is None
    assert await _risks_for_finding(test_session, positive["reference_number"]) == []
    assert await _junction_risk_ids(test_session, positive["id"]) == []
    assert positive["risk_ids"] in (None, [])

    flag_response = await client.post(
        f"/api/v1/audits/findings/{positive['id']}/flag-risk",
        headers=auth_headers,
        json={"severity": "high"},
    )
    assert flag_response.status_code == 200, flag_response.text

    test_session.expire_all()
    flagged_risks = await _risks_for_finding(test_session, positive["reference_number"])
    assert len(flagged_risks) == 1
    assert flag_response.json()["risk_ids"] == [flagged_risks[0].id]
    assert await _junction_risk_ids(test_session, positive["id"]) == [flagged_risks[0].id]


async def test_complete_run_materializes_finding_capa_and_risk(
    client,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """Completing a failed inspection response persists the complete downstream chain."""
    run, question = await _inspection_run(test_session, with_failed_response=True)
    assert question is not None
    run_id = run.id
    run_reference = run.reference_number
    question_id = question.id

    complete_response = await client.post(
        f"/api/v1/audits/runs/{run_id}/complete",
        headers=auth_headers,
    )
    assert complete_response.status_code == 200, complete_response.text
    assert complete_response.json()["status"] == "completed"

    test_session.expire_all()
    finding_result = await test_session.execute(
        select(AuditFinding).where(
            AuditFinding.tenant_id == 1,
            AuditFinding.run_id == run_id,
            AuditFinding.question_id == question_id,
        )
    )
    finding = finding_result.scalar_one()
    action = await _action_for_finding(test_session, finding.id)
    risks = await _risks_for_finding(test_session, finding.reference_number)

    assert finding.finding_type == "nonconformity"
    assert finding.severity == "high"
    assert action is not None
    assert action.source_id == finding.id
    assert len(risks) == 1
    assert run_reference in (risks[0].linked_audits or [])
    assert finding.reference_number in (risks[0].linked_audits or [])
    assert action.reference_number in (risks[0].linked_actions or [])
    assert finding.risk_ids_json == [risks[0].id]
    assert await _junction_risk_ids(test_session, finding.id) == [risks[0].id]


async def test_complete_run_requires_all_required_questions(
    client,
    test_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    """Required-question gate blocks completion when answers are missing."""
    run, _ = await _inspection_run(test_session, with_failed_response=False)
    section = AuditSection(
        template_id=run.template_id,
        title="Required gate",
        sort_order=1,
    )
    test_session.add(section)
    await test_session.flush()
    question = AuditQuestion(
        template_id=run.template_id,
        section_id=section.id,
        question_text="Is the control in place?",
        question_type="yes_no",
        positive_answer="yes",
        is_required=True,
        risk_weight=3,
        failure_triggers_action=True,
        sort_order=1,
    )
    test_session.add(question)
    await test_session.commit()

    blocked = await client.post(
        f"/api/v1/audits/runs/{run.id}/complete",
        headers=auth_headers,
    )
    assert blocked.status_code == 400, blocked.text
    payload = blocked.json()
    details = payload.get("error", {}).get("details") or payload.get("details") or {}
    assert question.id in (details.get("missing_question_ids") or [])
