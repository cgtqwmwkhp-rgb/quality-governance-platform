"""INV-C13: pack content overlays and HSG245 omit-id mapping. INV-C16: the ICAM factor payload."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.domain.models.capa import CAPAAction
from src.domain.models.investigation import CustomerPackAudience, InvestigationRun
from src.domain.models.investigation_finding import InvestigationFinding
from src.domain.models.rca_tools import CausalDepth, FishboneCategory, FishboneDiagram, FiveWhysAnalysis
from src.domain.services.investigation_factors_service import read_factors
from src.domain.services.investigation_pack_content import (
    event_details_pack_keys,
    expand_omitted_pack_keys,
    load_investigation_pack_sources,
    overlay_investigation_sections,
    serialize_capa_section,
    serialize_findings_section,
    serialize_icam_factors,
    serialize_rca_section,
)
from src.domain.services.investigation_service import InvestigationService

TENANT = 7
OTHER_TENANT = 8
ORGANISATIONAL = FishboneCategory.ORGANISATIONAL.value
DEFENCES = FishboneCategory.ABSENT_FAILED_DEFENCES.value


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


# ---------------------------------------------------------------------------
# ICAM contributing factors in the pack payload (INV-C16)
# ---------------------------------------------------------------------------


def _causes(*, tenant_extra: bool = False) -> dict:
    """A stored ``fishbone_diagrams.causes`` object in the shape INV-C12 writes."""
    causes: dict = {
        ORGANISATIONAL: [
            {
                "id": 4,
                "cause": "No refresher training schedule",
                "sub_causes": ["Budget withdrawn", "No owner named"],
                "depth": CausalDepth.UNDERLYING.value,
            },
            {"id": 7, "cause": "Guard removal needs no permit to work", "sub_causes": []},
        ],
        DEFENCES: [{"id": 9, "cause": "Interlock bypassed", "sub_causes": [], "depth": CausalDepth.ROOT.value}],
        FishboneDiagram.NEXT_FACTOR_ID_KEY: 10,
    }
    if tenant_extra:
        # A pre-DEC-1 6M key that no ICAM band exists for.
        causes["machine"] = [{"id": 2, "cause": "Conveyor belt worn"}]
    return causes


def _snapshot(**kwargs):
    return read_factors(_causes(**kwargs), investigation_id=7)


def test_serialize_icam_factors_carries_ids_categories_sub_causes_and_depth():
    payload = serialize_icam_factors(_snapshot())

    assert payload["factors"] == [
        {
            "id": 4,
            "category": ORGANISATIONAL,
            "cause": "No refresher training schedule",
            "sub_causes": ["Budget withdrawn", "No owner named"],
            "depth": "underlying",
        },
        {
            "id": 7,
            "category": ORGANISATIONAL,
            "cause": "Guard removal needs no permit to work",
            "sub_causes": [],
            "depth": None,
        },
        {"id": 9, "category": DEFENCES, "cause": "Interlock bypassed", "sub_causes": [], "depth": "root"},
    ]
    assert payload["unmapped_categories"] == []
    assert payload["unpresentable"] == 0
    # The investigation's primary key is not repeated on every factor.
    assert all("investigation_id" not in factor for factor in payload["factors"])


def test_serialize_icam_factors_reports_pre_dec1_6m_keys_without_recategorising_them():
    payload = serialize_icam_factors(_snapshot(tenant_extra=True))

    assert payload["unmapped_categories"] == ["machine"]
    assert payload["unpresentable"] == 1
    assert "Conveyor belt worn" not in str(payload["factors"])
    assert {factor["category"] for factor in payload["factors"]} <= {ORGANISATIONAL, DEFENCES}


def test_serialize_icam_factors_on_an_empty_diagram_is_empty_not_invented():
    payload = serialize_icam_factors(read_factors({}, investigation_id=7))

    assert payload == {"factors": [], "unmapped_categories": [], "unpresentable": 0}


def test_rca_section_omits_the_icam_key_entirely_when_factors_were_not_loaded():
    # Absent is not empty: a pack generated before INV-C16 never asked the
    # factors, so it must not read back as "no factors are recorded".
    section = serialize_rca_section({"root_cause": "x", "whys": []})

    assert "icam_factors" not in section
    assert overlay_investigation_sections(rca={"whys": []})["root-cause"].get("icam_factors") is None


def test_rca_section_carries_the_factors_alongside_the_legacy_text():
    rca = {"root_cause": "No permit", "whys": [], "contributing_factors": "leftover paragraph"}

    section = serialize_rca_section(rca, factors=_snapshot())

    # C18 retires the string reader; until then both shapes ship.
    assert section["contributing_factors"] == "leftover paragraph"
    assert len(section["icam_factors"]["factors"]) == 3


def test_generated_pack_content_carries_the_icam_factors_for_the_diagram():
    content, _, _ = _generate(_run(), findings=[], rca={"whys": []}, capa_actions=[], factors=_snapshot())

    factors = content["sections"]["root-cause"]["icam_factors"]
    assert [factor["id"] for factor in factors["factors"]] == [4, 7, 9]
    assert factors["factors"][0]["depth"] == "underlying"


def test_an_approved_root_cause_omit_withholds_the_icam_factors_with_the_section():
    investigation = _run(
        data={
            "sections": {"section_1_details": {"location": "Mill floor"}},
            "customer_pack_visibility": {"root-cause": {"omit_requested": True, "omit_approved": True}},
        }
    )

    content, _, _ = _generate(
        investigation,
        findings=[],
        rca={"root_cause": "No permit", "whys": []},
        capa_actions=[],
        factors=_snapshot(),
    )

    assert "root-cause" not in content["sections"]
    assert "root-cause" in content["omitted_sections"]
    assert "icam_factors" not in str(content["sections"])
    assert "No refresher training schedule" not in str(content)


def test_an_external_pack_carries_the_factors_that_the_redaction_pass_left():
    content, redaction_log, _ = InvestigationService.generate_customer_pack(
        investigation=_run(),
        audience=CustomerPackAudience.EXTERNAL_CUSTOMER,
        evidence_assets=[],
        generated_by_id=1,
        findings=[],
        rca={"whys": []},
        capa_actions=[],
        factors=_snapshot(),
    )

    # No factor field is an identity field, so the pass rewrites none of them —
    # the same treatment the contributing-factor text already gets.
    assert len(content["sections"]["root-cause"]["icam_factors"]["factors"]) == 3
    assert not [entry for entry in redaction_log if str(entry.get("field_path")).startswith("root-cause.icam")]


@pytest.fixture
async def factors_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        for table in (
            InvestigationRun.__table__,
            InvestigationFinding.__table__,
            FishboneDiagram.__table__,
            FiveWhysAnalysis.__table__,
            CAPAAction.__table__,
        ):
            await conn.run_sync(table.create)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed_run_and_diagram(db: AsyncSession, *, run_tenant: int, diagram_tenant: int) -> InvestigationRun:
    run = InvestigationRun(
        id=7,
        tenant_id=run_tenant,
        template_id=1,
        assigned_entity_type="incident",
        assigned_entity_id=42,
        status="in_progress",
        title="Fork lift near miss",
        reference_number="INV-7",
        data={},
        version=1,
    )
    db.add(run)
    db.add(
        FishboneDiagram(
            tenant_id=diagram_tenant,
            investigation_id=7,
            entity_type="incident",
            entity_id=42,
            effect_statement="Operator reached into the mill",
            causes=_causes(),
        )
    )
    await db.commit()
    return run


@pytest.mark.asyncio
async def test_pack_sources_load_this_tenants_factors_from_the_stored_diagram(factors_db):
    run = await _seed_run_and_diagram(factors_db, run_tenant=TENANT, diagram_tenant=TENANT)

    sources = await load_investigation_pack_sources(factors_db, investigation=run, tenant_id=TENANT)

    assert sources.factors is not None
    assert [factor.id for factor in sources.factors.factors] == [4, 7, 9]
    assert serialize_icam_factors(sources.factors)["factors"][0]["cause"] == "No refresher training schedule"


@pytest.mark.asyncio
async def test_another_tenants_diagram_never_reaches_this_tenants_pack(factors_db):
    # The run is this tenant's; the diagram row is not. The factors reader
    # re-filters on tenant_id, so the pack gets an empty diagram rather than
    # another organisation's contributing factors.
    run = await _seed_run_and_diagram(factors_db, run_tenant=TENANT, diagram_tenant=OTHER_TENANT)

    sources = await load_investigation_pack_sources(factors_db, investigation=run, tenant_id=TENANT)

    assert sources.factors is not None
    assert sources.factors.factors == []
    content, _, _ = _generate(run, findings=[], rca={"whys": []}, capa_actions=[], factors=sources.factors)
    assert content["sections"]["root-cause"]["icam_factors"]["factors"] == []
    assert "No refresher training schedule" not in str(content)


@pytest.mark.asyncio
async def test_pack_sources_fail_closed_on_a_tenant_mismatch_without_consulting_the_factors():
    db = AsyncMock()
    investigation = SimpleNamespace(id=7, tenant_id=TENANT)

    sources = await load_investigation_pack_sources(db, investigation=investigation, tenant_id=OTHER_TENANT)

    # None, not an empty snapshot: nothing was consulted, so the pack states
    # nothing rather than claiming the diagram is empty.
    assert sources.factors is None
    db.execute.assert_not_called()
