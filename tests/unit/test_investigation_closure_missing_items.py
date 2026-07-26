"""PX-134: closure validation must name the blocking section, not just its code.

``reason_codes`` alone ("MISSING_REQUIRED_SECTION") was rendered raw to the
user, with no indication of which section or how to resolve it. ``missing_items``
carries the human labels alongside the keys so the UI can name the blocker.
"""

from __future__ import annotations

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


STRUCTURE = {
    "sections": [
        {
            "id": "sec_root_cause",
            "name": "Root cause analysis",
            "min_level": "minimal",
            "fields": [
                {"id": "immediate_cause", "label": "Immediate cause", "type": "text", "required": True},
                {"id": "evidence", "label": "Supporting evidence", "type": "array", "required": True},
                {"id": "notes", "label": "Notes", "type": "text", "required": False},
            ],
        }
    ]
}


class TestClosureMissingItems:
    @pytest.mark.asyncio
    async def test_missing_section_is_named(self):
        result = await _run_validate(_inv(data={}), _tmpl(STRUCTURE))

        assert ClosureReasonCode.MISSING_REQUIRED_SECTION in result.reason_codes
        assert len(result.missing_items) == 1
        item = result.missing_items[0]
        assert item.code == ClosureReasonCode.MISSING_REQUIRED_SECTION
        assert item.section_key == "sec_root_cause"
        assert item.section_label == "Root cause analysis"
        assert item.field_key is None
        assert item.path == "sec_root_cause"

    @pytest.mark.asyncio
    async def test_missing_field_carries_both_labels(self):
        data = {"sections": {"sec_root_cause": {"immediate_cause": "  ", "evidence": ["photo"]}}}
        result = await _run_validate(_inv(data=data), _tmpl(STRUCTURE))

        assert result.missing_items
        item = next(i for i in result.missing_items if i.field_key == "immediate_cause")
        assert item.code == ClosureReasonCode.MISSING_REQUIRED_FIELD
        assert item.section_label == "Root cause analysis"
        assert item.field_label == "Immediate cause"
        assert item.path == "sec_root_cause.immediate_cause"

    @pytest.mark.asyncio
    async def test_empty_array_is_reported_as_its_own_code(self):
        data = {"sections": {"sec_root_cause": {"immediate_cause": "Wet floor", "evidence": []}}}
        result = await _run_validate(_inv(data=data), _tmpl(STRUCTURE))

        assert result.reason_codes == [ClosureReasonCode.INVALID_ARRAY_EMPTY]
        assert [i.path for i in result.missing_items] == ["sec_root_cause.evidence"]
        assert result.missing_items[0].field_label == "Supporting evidence"

    @pytest.mark.asyncio
    async def test_missing_fields_stays_in_step_with_missing_items(self):
        result = await _run_validate(_inv(data={}), _tmpl(STRUCTURE))

        assert result.missing_fields == [i.path for i in result.missing_items]

    @pytest.mark.asyncio
    async def test_falls_back_to_the_key_when_the_template_has_no_labels(self):
        structure = {
            "sections": [
                {
                    "id": "sec_unlabelled",
                    "min_level": "minimal",
                    "fields": [{"id": "f1", "type": "text", "required": True}],
                }
            ]
        }
        result = await _run_validate(_inv(data={}), _tmpl(structure))

        assert result.missing_items[0].section_label == "sec_unlabelled"

    @pytest.mark.asyncio
    async def test_complete_section_reports_nothing(self):
        data = {"sections": {"sec_root_cause": {"immediate_cause": "Wet floor", "evidence": ["photo.jpg"]}}}
        result = await _run_validate(_inv(data=data), _tmpl(STRUCTURE))

        assert result.status == "OK"
        assert result.missing_items == []

    @pytest.mark.asyncio
    async def test_template_not_found_returns_no_items_rather_than_guessing(self):
        result = await _run_validate(_inv(), None)

        assert result.reason_codes == [ClosureReasonCode.TEMPLATE_NOT_FOUND]
        assert result.missing_items == []


class TestMissingItemsPayload:
    """The route serializer must survive a result object without ``missing_items``."""

    def test_serializes_section_and_field_blockers(self):
        from src.api.routes.investigations import _missing_items_to_payload
        from src.domain.services.investigation_service import ClosureMissingItem

        validation = MagicMock()
        validation.missing_items = [
            ClosureMissingItem(
                code=ClosureReasonCode.MISSING_REQUIRED_SECTION,
                section_key="sec_a",
                section_label="Section A",
            ),
            ClosureMissingItem(
                code=ClosureReasonCode.MISSING_REQUIRED_FIELD,
                section_key="sec_a",
                section_label="Section A",
                field_key="f1",
                field_label="Field one",
            ),
        ]

        payload = _missing_items_to_payload(validation)

        assert payload[0]["path"] == "sec_a"
        assert payload[0]["field_key"] is None
        assert payload[1]["path"] == "sec_a.f1"
        assert payload[1]["field_label"] == "Field one"

    def test_returns_empty_for_a_result_without_the_attribute(self):
        from src.api.routes.investigations import _missing_items_to_payload

        assert _missing_items_to_payload(object()) == []
