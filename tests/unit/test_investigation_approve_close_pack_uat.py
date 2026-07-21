"""ACT-050: approve/close/customer-pack must not 500 on not-ready / response shape."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.schemas.investigation import InvestigationPackGeneratedResponse
from src.domain.models.investigation import InvestigationStatus
from src.domain.services.investigation_service import InvestigationService


def test_customer_pack_response_accepts_dict_content():
    """Regression: content was typed as str → ResponseValidationError 500 after persist."""
    payload = InvestigationPackGeneratedResponse(
        pack_id=1,
        pack_uuid="2035d36e-8af1-4cf2-9796-22f41646e284",
        audience="internal_customer",
        investigation_id=6,
        investigation_reference="REF-2026-0006",
        generated_at=datetime.now(timezone.utc),
        content={"sections": {"section_1_details": {"reference_number": "INC-1"}}, "title": "t"},
        redaction_log=[],
        included_assets=[],
        checksum_sha256="abc",
    )
    assert payload.content["sections"]["section_1_details"]["reference_number"] == "INC-1"


def test_generate_customer_pack_handles_list_sections():
    from src.domain.models.investigation import CustomerPackAudience

    investigation = MagicMock()
    investigation.reference_number = "REF-1"
    investigation.title = "Title"
    investigation.status = InvestigationStatus.IN_PROGRESS
    investigation.level = "medium"
    investigation.data = {
        "sections": [
            {"id": "section_1", "fields": {"reporter_name": "Ada"}},
        ]
    }

    with patch.object(InvestigationService, "approved_customer_omits", return_value=[]):
        content, _log, _assets = InvestigationService.generate_customer_pack(
            investigation=investigation,
            audience=CustomerPackAudience.INTERNAL_CUSTOMER,
            evidence_assets=[],
            generated_by_id=1,
        )

    assert "section_1" in content["sections"]
    assert content["sections"]["section_1"]["reporter_name"] == "Ada"


@pytest.mark.asyncio
async def test_ensure_close_returns_400_with_reasons():
    from src.api.routes.investigations import _ensure_investigation_ready_to_close
    from src.domain.exceptions import BadRequestError

    investigation = MagicMock()
    current_user = MagicMock(tenant_id=1)
    db = AsyncMock()

    with (
        patch(
            "src.api.routes.investigations._collect_closure_reasons",
            new=AsyncMock(
                return_value=(
                    ["STATUS_NOT_COMPLETE", "LEVEL_NOT_SET", "MISSING_REQUIRED_SECTION"],
                    [],
                )
            ),
        ),
        pytest.raises(BadRequestError) as exc_info,
    ):
        await _ensure_investigation_ready_to_close(
            db,
            investigation=investigation,
            investigation_id=7,
            current_user=current_user,
        )

    assert exc_info.value.http_status == 400
    assert exc_info.value.code == "CLOSURE_VALIDATION_FAILED"
    assert "STATUS_NOT_COMPLETE" in exc_info.value.details["reasons"]
