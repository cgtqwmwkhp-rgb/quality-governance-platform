"""Unit tests for InvestigationService.validate_closure hardening."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.investigation_service import ClosureReasonCode, InvestigationService


def _inv(*, level="medium", data=None, template_id=1):
    obj = MagicMock()
    obj.template_id = template_id
    obj.level = level
    obj.data = data if data is not None else {}
    return obj


def _tmpl(structure):
    obj = MagicMock()
    obj.structure = structure
    return obj


async def _run_validate(investigation, template):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = template
    db.execute = AsyncMock(return_value=result)
    with patch.object(
        InvestigationService,
        "get_investigation",
        AsyncMock(return_value=investigation),
    ):
        return await InvestigationService.validate_closure(
            db,
            investigation_id=1,
            tenant_id=1,
        )


class TestValidateClosureHardening:
    @pytest.mark.asyncio
    async def test_sections_dict_does_not_raise(self):
        """Builder-shaped sections map must not AttributeError → 500."""
        result = await _run_validate(
            _inv(data={"sections": {}}),
            _tmpl({"sections": {"summary": {"id": "summary", "fields": []}}}),
        )
        assert result.status in {"OK", "BLOCKED"}
        assert ClosureReasonCode.TEMPLATE_NOT_FOUND not in [
            c.value if hasattr(c, "value") else c for c in result.reason_codes
        ]

    @pytest.mark.asyncio
    async def test_none_section_skipped(self):
        result = await _run_validate(
            _inv(),
            _tmpl({"sections": [None, {"id": "s1", "fields": [{"id": "f1", "required": True}]}]}),
        )
        codes = [c.value if hasattr(c, "value") else c for c in result.reason_codes]
        assert ClosureReasonCode.MISSING_REQUIRED_SECTION in codes

    @pytest.mark.asyncio
    async def test_wrapped_from_record_data_reads_nested_sections(self):
        """create_from_record stores data under data.sections — must validate there."""
        structure = {
            "sections": [
                {
                    "id": "section_1_details",
                    "fields": [
                        {"id": "description", "type": "text", "required": True},
                    ],
                }
            ]
        }
        data = {"sections": {"section_1_details": {"description": "Prefill from incident"}}}
        result = await _run_validate(_inv(data=data), _tmpl(structure))
        codes = [c.value if hasattr(c, "value") else c for c in result.reason_codes]
        assert ClosureReasonCode.MISSING_REQUIRED_SECTION not in codes
        assert ClosureReasonCode.MISSING_REQUIRED_FIELD not in codes

    @pytest.mark.asyncio
    async def test_non_dict_data_treated_as_empty(self):
        result = await _run_validate(
            _inv(data=["not", "a", "dict"]),  # type: ignore[arg-type]
            _tmpl({"sections": [{"id": "s1", "fields": [{"id": "f1", "type": "text", "required": True}]}]}),
        )
        codes = [c.value if hasattr(c, "value") else c for c in result.reason_codes]
        assert ClosureReasonCode.MISSING_REQUIRED_SECTION in codes
        assert isinstance(result.checked_at_utc, datetime)
        assert result.checked_at_utc.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_section_data_scalar_does_not_raise(self):
        result = await _run_validate(
            _inv(data={"s1": "oops"}),
            _tmpl({"sections": [{"id": "s1", "fields": [{"id": "f1", "type": "text", "required": True}]}]}),
        )
        codes = [c.value if hasattr(c, "value") else c for c in result.reason_codes]
        assert ClosureReasonCode.MISSING_REQUIRED_SECTION in codes
