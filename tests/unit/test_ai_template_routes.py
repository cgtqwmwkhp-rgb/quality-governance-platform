from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.api.routes.ai_templates import PromptTemplateRequest, generate_template


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
