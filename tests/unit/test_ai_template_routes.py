from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from src.api.routes.ai_templates import AI_TEMPLATE_UNAVAILABLE_DETAIL, PromptTemplateRequest, generate_template


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

    service = SimpleNamespace(prompt_to_template=AsyncMock(return_value=expected_sections))

    with patch("src.api.routes.ai_templates.GeminiAIService", return_value=service):
        result = await generate_template(
            PromptTemplateRequest(prompt="Generate an ISO 9001 leadership checklist"),
            db=SimpleNamespace(),
            user=SimpleNamespace(),
        )

    assert result == expected_sections
    service.prompt_to_template.assert_awaited_once_with("Generate an ISO 9001 leadership checklist")


@pytest.mark.asyncio
async def test_generate_template_hides_upstream_error_details() -> None:
    service = SimpleNamespace(prompt_to_template=AsyncMock(side_effect=RuntimeError("provider token=secret")))

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
