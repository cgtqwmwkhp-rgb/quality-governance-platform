from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.routes.ai_templates import (
    AI_TEMPLATE_UNAVAILABLE_DETAIL,
    GenerateFromBriefRequest,
    PromptTemplateRequest,
    generate_from_brief,
    generate_template,
)


@pytest.mark.asyncio
async def test_generate_template_route_returns_sections() -> None:
    expected_sections = [
        {
            "id": "section-1",
            "title": "Leadership",
            "description": "Management checks",
            "questions": [
                {
                    "id": "question-1",
                    "text": "Is the policy current?",
                    "type": "yes_no",
                    "required": True,
                    "weight": 1,
                    "riskLevel": "medium",
                    "evidenceRequired": False,
                    "isoClause": "5.2",
                    "guidance": "Review the signed policy",
                }
            ],
        }
    ]

    service = SimpleNamespace(
        is_configured=MagicMock(return_value=True),
        prompt_to_template=AsyncMock(return_value=expected_sections),
    )

    with patch("src.api.routes.ai_templates.GeminiAIService", return_value=service):
        result = await generate_template(
            PromptTemplateRequest(prompt="Generate an ISO 9001 leadership checklist"),
            db=SimpleNamespace(),
            user=SimpleNamespace(),
        )

    assert result == expected_sections
    service.prompt_to_template.assert_awaited_once_with("Generate an ISO 9001 leadership checklist")


@pytest.mark.asyncio
async def test_generate_template_hides_upstream_error_details(caplog: pytest.LogCaptureFixture) -> None:
    service = SimpleNamespace(
        is_configured=MagicMock(return_value=True),
        prompt_to_template=AsyncMock(side_effect=RuntimeError("provider token=secret")),
    )

    with patch("src.api.routes.ai_templates.GeminiAIService", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            await generate_template(
                PromptTemplateRequest(prompt="Generate an ISO 9001 leadership checklist"),
                db=SimpleNamespace(),
                user=SimpleNamespace(),
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == AI_TEMPLATE_UNAVAILABLE_DETAIL
    assert "secret" not in exc_info.value.detail
    assert any("generate-template failed" in r.message for r in caplog.records)
    assert any("RuntimeError" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_generate_template_early_fails_when_gemini_not_configured(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = SimpleNamespace(is_configured=MagicMock(return_value=False))

    with patch("src.api.routes.ai_templates.GeminiAIService", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            await generate_template(
                PromptTemplateRequest(prompt="Generate an ISO 9001 leadership checklist"),
                db=SimpleNamespace(),
                user=SimpleNamespace(),
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == AI_TEMPLATE_UNAVAILABLE_DETAIL
    assert any("GeminiAIService not configured" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_generate_from_brief_early_fails_when_gemini_not_configured(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = SimpleNamespace(is_configured=MagicMock(return_value=False))
    user = SimpleNamespace(tenant_id=1)

    with (
        patch("src.api.routes.ai_templates.GeminiAIService", return_value=service),
        patch("src.api.routes.ai_templates.require_tenant_id", return_value=1),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await generate_from_brief(
                GenerateFromBriefRequest(brief={"brief_id": "b1", "case_refs": []}),
                db=SimpleNamespace(),
                user=user,
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == AI_TEMPLATE_UNAVAILABLE_DETAIL
    assert any("GeminiAIService not configured" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_generate_from_brief_logs_exception_type_before_503(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = SimpleNamespace(is_configured=MagicMock(return_value=True))
    user = SimpleNamespace(tenant_id=1)
    orch = SimpleNamespace(compose_generation_prompt=MagicMock(return_value="PROMPT"))
    pipeline = SimpleNamespace(
        generate=AsyncMock(side_effect=RuntimeError("EMPTY_TEMPLATE")),
    )

    with (
        patch("src.api.routes.ai_templates.GeminiAIService", return_value=service),
        patch("src.api.routes.ai_templates.require_tenant_id", return_value=1),
        patch(
            "src.domain.services.audit_builder_orchestrator.AuditBuilderOrchestrator",
            return_value=orch,
        ),
        patch(
            "src.domain.services.audit_builder_generation_pipeline.AuditBuilderGenerationPipeline",
            return_value=pipeline,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await generate_from_brief(
                GenerateFromBriefRequest(brief={"brief_id": "b1", "case_refs": []}),
                db=SimpleNamespace(),
                user=user,
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == AI_TEMPLATE_UNAVAILABLE_DETAIL
    assert any("generate-from-brief failed" in r.message for r in caplog.records)
    assert any("RuntimeError" in r.message and "EMPTY_TEMPLATE" in r.message for r in caplog.records)
