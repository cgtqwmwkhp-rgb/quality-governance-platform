"""INV-C13: pack content overlays and HSG245 omit-id mapping."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.models.investigation import CustomerPackAudience
from src.domain.services.investigation_pack_content import (
    event_details_pack_keys,
    expand_omitted_pack_keys,
    load_investigation_pack_sources,
    overlay_investigation_sections,
    serialize_capa_section,
    serialize_findings_section,
    serialize_rca_section,
)
from src.domain.services.investigation_service import InvestigationService


def _run(**overrides: object) -> SimpleNamespace:
    investigation = SimpleNamespace(
        reference_number="INV-2026-0013",
        title="Guard missing on the mill",
        status=SimpleNamespace(value="completed"),
        level=SimpleNamespace(value="high"),
        data={
            "sections": {
                "section_1_details": {"location": "Mill floor", "incident_date": "2026-05-17"},
                "section_3_investigation_findings": {"findings": "stale concatenated string"},
            }
        },
    )
    for key, value in overrides.items():
        setattr(investigation, key, value)
    return investigation


def _generate(investigation, **kwargs):
    return InvestigationService.generate_customer_pack(
        investigation=investigation,
        audience=CustomerPackAudience.INTERNAL_CUSTOMER,
        evidence_assets=[],
        generated_by_id=1,
        **kwargs,
    )


def test_hsg245_findings_omit_withholds_the_findings_section_not_event_details():
    investigation = _run(
        data={
            "sections": {"section_1_details": {"location": "Mill floor"}},
            "customer_pack_visibility": {
                "findings": {"omit_requested": True, "omit_approved": True},
            },
        }
    )
    content, redaction_log, _ = _generate(
        investigation,
        findings=[{"body": "The interlock was bypassed"}],
        rca={"whys": [{"level": 1, "why": "", "answer": "operator reached in"}], "root_cause": "bypass"},
        capa_actions=[],
    )
    assert "findings" not in content["sections"]
    assert "section_1_details" in content["sections"]
    assert content["sections"]["section_1_details"]["location"] == "Mill floor"
    assert "findings" in content["omitted_sections"]
    assert "The interlock was bypassed" not in str(content["sections"])
    assert any(
        entry.get("field_path") == "findings" and entry.get("redaction_type") == "SECTION_OMIT_APPROVED"
        for entry in redaction_log
    )


def test_hsg245_event_details_omit_withholds_section_1_details_actually_present():
    investigation = _run(
        data={
            "sections": {
                "section_1_details": {"location": "Mill floor"},
                "section_2_immediate_actions": {"actions_taken": "Isolated the mill"},
            },
            "customer_pack_visibility": {
                "event-details": {"omit_requested": True, "omit_approved": True},
            },
        }
    )
    content, _, _ = _generate(investigation, findings=[], rca={"whys": []}, capa_actions=[])
    assert "section_1_details" not in content["sections"]
    assert "section_2_immediate_actions" in content["sections"]
    assert "findings" in content["sections"]
    assert "event-details" in content["omitted_sections"]


def test_pack_from_finding_why_and_capa_contains_those_not_only_section_1_details():
    investigation = _run()
    content, _, _ = _generate(
        investigation,
        findings=[SimpleNamespace(body="Guard was missing from the mill")],
        rca={
            "problem_statement": "Operator reached into the mill",
            "whys": [
                {"level": 1, "why": "Why was the guard off?", "answer": "It had been removed for cleaning"},
                {"level": 2, "why": "", "answer": "", "evidence": ""},
            ],
            "root_cause": "No permit for guard removal",
            "contributing_factors": "Cleaning was treated as informal",
        },
        capa_actions=[
            SimpleNamespace(
                title="CAPA: It had been removed for cleaning",
                reference_number="CAPA-2026-0042",
                why_level=1,
            )
        ],
    )
    sections = content["sections"]
    assert "section_1_details" in sections
    assert "findings" in sections
    assert "root-cause" in sections
    assert "capa" in sections
    assert sections["findings"]["items"] == [{"body": "Guard was missing from the mill"}]
    assert sections["root-cause"]["whys"] == [
        {"level": 1, "why": "Why was the guard off?", "answer": "It had been removed for cleaning"}
    ]
    assert sections["root-cause"]["root_cause"] == "No permit for guard removal"
    assert sections["root-cause"]["contributing_factors"] == "Cleaning was treated as informal"
    assert sections["capa"]["items"] == [
        {"title": "CAPA: It had been removed for cleaning", "reference": "CAPA-2026-0042", "why_level": 1}
    ]
    # Overlay replaces the concatenated findings string rather than reprinting it.
    assert "section_3_investigation_findings" not in sections
    assert "stale concatenated string" not in str(sections)
    assert "fishbone" not in sections
    assert "people" not in sections["root-cause"]
    assert "icam" not in str(sections["root-cause"]).lower()


def test_empty_findings_why_and_capa_are_stated_empty_and_invent_nothing():
    investigation = _run(data={"sections": {"section_1_details": {"location": "yard"}}})
    content, _, _ = _generate(investigation, findings=[], rca={"whys": [], "root_cause": ""}, capa_actions=[])
    assert content["sections"]["findings"]["items"] == []
    assert content["sections"]["root-cause"]["whys"] == []
    assert content["sections"]["root-cause"]["root_cause"] == ""
    assert content["sections"]["capa"]["items"] == []
    assert "invent" not in str(content["sections"]).lower()
    assert serialize_findings_section([])["items"] == []
    assert serialize_capa_section([])["items"] == []


def test_empty_capa_overlay_preserves_written_corrective_action_prose():
    investigation = _run(
        data={
            "sections": {
                "section_1_details": {"location": "yard"},
                "section_5_corrective_actions": {"corrective_actions": "Replace the damaged guard before restart"},
            }
        }
    )

    content, _, _ = _generate(investigation, findings=[], rca=None, capa_actions=[])

    assert content["sections"]["section_5_corrective_actions"] == {
        "corrective_actions": "Replace the damaged guard before restart"
    }
    assert content["sections"]["capa"]["items"] == []


def test_without_overlays_the_pack_still_copies_source_sections_only():
    investigation = _run()
    content, _, _ = _generate(investigation)
    assert set(content["sections"]) == {"section_1_details", "section_3_investigation_findings"}
    assert "findings" not in content["sections"]
    assert "capa" not in content["sections"]


def test_expand_omitted_pack_keys_maps_hsg245_ids_and_keeps_literal_keys():
    present = {"section_1_details", "section_2_immediate_actions", "findings", "root-cause"}
    withheld = expand_omitted_pack_keys(["findings", "root-cause", "section_1_details"], present)
    assert "findings" in withheld
    assert "section_3_investigation_findings" in withheld
    assert "root-cause" in withheld
    assert "rca" in withheld
    assert "section_1_details" in withheld
    event_keys = event_details_pack_keys(present)
    assert event_keys == {"section_1_details"}
    withheld_event = expand_omitted_pack_keys(["event-details"], present)
    assert "section_1_details" in withheld_event
    assert "findings" not in withheld_event


def test_serialize_does_not_copy_icam_or_fishbone_keys():
    rca = serialize_rca_section(
        {
            "root_cause": "procedure missing",
            "contributing_factors": "leftover textarea",
            "whys": [{"level": 1, "why": "", "answer": "the guard was off"}],
            "fishbone": {"people": "invented"},
            "icam": [{"category": "acts"}],
        }
    )
    assert rca["contributing_factors"] == "leftover textarea"
    assert "fishbone" not in rca
    assert "icam" not in rca
    overlay = overlay_investigation_sections(findings=[], rca=rca, capa_actions=[])
    assert set(overlay) == {"findings", "root-cause", "capa"}


@pytest.mark.asyncio
async def test_load_pack_sources_fail_closed_on_tenant_mismatch():
    db = AsyncMock()
    investigation = SimpleNamespace(id=7, tenant_id=1)
    sources = await load_investigation_pack_sources(db, investigation=investigation, tenant_id=99)
    assert sources.findings == []
    assert sources.rca is None
    assert sources.capa_actions == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_load_pack_sources_fail_closed_when_tenant_is_missing():
    db = AsyncMock()
    investigation = SimpleNamespace(id=7, tenant_id=None)
    sources = await load_investigation_pack_sources(db, investigation=investigation, tenant_id=1)
    assert sources.findings == []
    assert sources.rca is None
    db.execute.assert_not_called()
