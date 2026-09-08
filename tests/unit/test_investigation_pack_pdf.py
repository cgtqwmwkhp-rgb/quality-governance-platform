"""Unit tests for the investigation customer pack PDF renderer (PX-143)."""

from __future__ import annotations

import builtins
import io
import re

import pytest

from src.domain.services import investigation_pack_pdf as pack_pdf
from src.domain.services.investigation_pack_pdf import (
    InvestigationPackPdfService,
    chronology_feed,
    confidentiality_notice,
    count_field_redactions,
    format_field_value,
    humanise_key,
    summarise_redactions,
)


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(data)).pages)


def _pack(**overrides) -> dict:
    pack = {
        "pack_uuid": "6f1c2d3e-0000-4000-8000-abcdefabcdef",
        "audience": "external_customer",
        "investigation_reference": "INV-2026-0007",
        "investigation_title": "Collision on the A1",
        "generated_at": "2026-07-20T10:00:00+00:00",
        "checksum_sha256": "a" * 64,
        "content": {
            "investigation_reference": "INV-2026-0007",
            "title": "Collision on the A1",
            "status": "completed",
            "level": "high",
            "sections": {
                "section_1_details": {
                    "incident_date": "2026-05-17",
                    "site_conditions": "Wet road surface, poor visibility",
                },
                "section_3_investigation_findings": {
                    "root_cause": "Brake maintenance interval exceeded",
                    "contributing_factors": ["Missed inspection", "No pre-use check"],
                },
            },
            "omitted_sections": ["section_5_internal_commentary"],
        },
        "redaction_log": [
            {"field_path": "section_1_details.driver_name", "redaction_type": "PII_REDACTED"},
            {"field_path": "section_1_details.reporter_name", "redaction_type": "PII_REDACTED"},
            {"field_path": "section_5_internal_commentary", "redaction_type": "SECTION_OMIT_APPROVED"},
        ],
        "included_assets": [
            {"asset_id": 1, "title": "Dashcam still", "asset_type": "photo", "included": True},
            {
                "asset_id": 2,
                "title": "Internal review note",
                "asset_type": "document",
                "included": False,
                "exclusion_reason": "INTERNAL_ONLY",
            },
        ],
    }
    pack.update(overrides)
    return pack


class TestPackPdfBytes:
    def test_renders_a_real_pdf_document(self) -> None:
        out = InvestigationPackPdfService().build_pdf_bytes(_pack(), organisation_name="Plantexpand")

        assert isinstance(out, bytes)
        assert out.startswith(b"%PDF-")
        assert out.rstrip().endswith(b"%%EOF")
        # A single near-empty page would be a few hundred bytes; this must carry content.
        assert len(out) > 2000

    def test_renders_when_pack_content_is_empty(self) -> None:
        out = InvestigationPackPdfService().build_pdf_bytes(_pack(content={}, redaction_log=[], included_assets=[]))

        assert out.startswith(b"%PDF-")

    def test_renders_when_content_is_not_a_mapping(self) -> None:
        out = InvestigationPackPdfService().build_pdf_bytes(
            _pack(content=None, redaction_log=None, included_assets=None)
        )

        assert out.startswith(b"%PDF-")

    def test_non_latin1_characters_do_not_break_the_render(self) -> None:
        out = InvestigationPackPdfService().build_pdf_bytes(
            _pack(
                content={
                    "title": "Collision — Ystrad Mynach",
                    "sections": {"notes": {"detail": "Driver said “no warning” — 20°C"}},
                }
            )
        )

        assert out.startswith(b"%PDF-")

    def test_invalid_brand_colour_falls_back_instead_of_failing(self) -> None:
        out = InvestigationPackPdfService().build_pdf_bytes(_pack(), primary_color="not-a-colour")

        assert out.startswith(b"%PDF-")

    def test_fails_closed_when_fpdf_is_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "fpdf" or name.startswith("fpdf."):
                raise ModuleNotFoundError("No module named 'fpdf'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        with pytest.raises(RuntimeError, match="fpdf2 is not installed"):
            InvestigationPackPdfService().build_pdf_bytes(_pack())


class TestPackPdfFilename:
    def test_uses_reference_and_pack_uuid_prefix(self) -> None:
        name = InvestigationPackPdfService.pdf_filename("INV-2026-0007", "6f1c2d3e-0000")

        assert name == "investigation-report-INV-2026-0007-6f1c2d3e.pdf"

    def test_strips_path_separators_from_the_reference(self) -> None:
        name = InvestigationPackPdfService.pdf_filename("../../etc/passwd", "abcd1234")

        assert "/" not in name
        assert ".." not in name.replace("..pdf", "")
        assert re.fullmatch(r"investigation-report-[\w.\-]+-abcd1234\.pdf", name)

    def test_tolerates_missing_reference_and_uuid(self) -> None:
        assert InvestigationPackPdfService.pdf_filename(None, None) == "investigation-report-pack-pack.pdf"


class TestFieldRendering:
    def test_humanises_stored_keys(self) -> None:
        assert humanise_key("section_1_details") == "Section 1 details"
        assert humanise_key("root_cause") == "Root cause"
        assert humanise_key("") == "Untitled"

    def test_missing_values_are_stated_not_blank(self) -> None:
        assert format_field_value(None) == "Not recorded"
        assert format_field_value("") == "Not recorded"
        assert format_field_value("   ") == "Not recorded"
        assert format_field_value([]) == "None recorded"
        assert format_field_value({}) == "None recorded"

    def test_zero_and_false_are_not_treated_as_missing(self) -> None:
        assert format_field_value(0) == "0"
        assert format_field_value(False) == "No"
        assert format_field_value(True) == "Yes"

    def test_lists_and_maps_render_every_entry(self) -> None:
        assert format_field_value(["a", "b"]) == "- a\n- b"
        assert format_field_value({"root_cause": "Wear"}) == "Root cause: Wear"


class TestRedactionSummary:
    def test_counts_by_type(self) -> None:
        assert summarise_redactions(_pack()["redaction_log"]) == [
            ("PII_REDACTED", 2),
            ("SECTION_OMIT_APPROVED", 1),
        ]

    def test_tolerates_missing_or_malformed_logs(self) -> None:
        assert summarise_redactions(None) == []
        assert summarise_redactions("nonsense") == []
        assert summarise_redactions([None, 3, {}]) == [("REDACTION", 1)]


class TestFieldRedactionCount:
    def test_counts_rewritten_fields_and_ignores_approved_section_omits(self) -> None:
        assert count_field_redactions(_pack()["redaction_log"]) == 2

    def test_counts_every_field_redaction_label_the_service_emits(self) -> None:
        # The service writes IDENTITY_REDACTION, the contract doc says REDACTED_PII and the
        # fixture above says PII_REDACTED. Counting one name would undercount real packs.
        log = [
            {"redaction_type": "IDENTITY_REDACTION"},
            {"redaction_type": "PII_REDACTED"},
            {"redaction_type": "REDACTED_PII"},
            {"redaction_type": "SECTION_OMIT_APPROVED"},
        ]

        assert count_field_redactions(log) == 3

    def test_tolerates_missing_or_malformed_logs(self) -> None:
        assert count_field_redactions(None) == 0
        assert count_field_redactions("nonsense") == 0
        assert count_field_redactions([None, 3]) == 0


class TestConfidentialityNotice:
    def test_external_pack_does_not_claim_redaction_that_did_not_happen(self) -> None:
        # REF-2026-0012 shipped externally with an empty log: the description held the only
        # identifying content and no field matched the identity allow-list.
        notice = confidentiality_notice("external_customer", [])

        assert "No fields were redacted from the sections below." in notice
        assert "Personal identities are redacted" not in notice

    def test_external_pack_reports_the_number_actually_redacted(self) -> None:
        assert "1 field was redacted" in confidentiality_notice(
            "external_customer", [{"redaction_type": "IDENTITY_REDACTION"}]
        )
        assert "2 fields were redacted" in confidentiality_notice("external_customer", _pack()["redaction_log"])

    def test_external_pack_always_states_that_narrative_is_not_redacted(self) -> None:
        for log in ([], [{"redaction_type": "IDENTITY_REDACTION"}]):
            notice = confidentiality_notice("external_customer", log)

            assert "Narrative text is reproduced as written" in notice
            assert "review this pack before releasing it" in notice

    def test_external_notice_survives_a_malformed_log(self) -> None:
        notice = confidentiality_notice("external_customer", "nonsense")

        assert "No fields were redacted from the sections below." in notice
        assert "Narrative text is reproduced as written" in notice

    def test_internal_pack_wording_is_unchanged(self) -> None:
        notice = confidentiality_notice("internal_customer", [])

        assert "Identities are retained" in notice
        assert "Narrative text is reproduced as written" not in notice

    def test_unknown_audience_gets_no_notice_rather_than_a_wrong_one(self) -> None:
        assert confidentiality_notice("regulator", []) == ""
        assert confidentiality_notice(None, []) == ""


class TestPackBranding:
    def test_default_brand_is_plantexpand_primary_not_tailwind_blue(self) -> None:
        assert pack_pdf._DEFAULT_BRAND_RGB == (78, 118, 10)
        assert pack_pdf._DEFAULT_BRAND_RGB != (59, 130, 246)

    def test_fixed_cell_text_is_ellipsized_to_its_rendered_width(self) -> None:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)

        fitted = pack_pdf._fit_cell_text(pdf, "A very long tenant organisation name " * 10, 110)

        assert fitted.endswith("...")
        assert pdf.get_string_width(fitted) <= 110

    def test_header_wordmark_footer_and_page_numbers_are_on_the_page(self) -> None:
        out = InvestigationPackPdfService().build_pdf_bytes(_pack(), organisation_name="Plantexpand Ltd")
        text = _pdf_text(out)

        assert "PLANTEXPAND" in text
        assert "Plantexpand Ltd" in text
        assert "Page 1 of" in text
        assert "External customer pack" in text
        assert "2 fields were redacted" in text

    def test_long_organisation_name_cannot_displace_wordmark_or_page_number(self) -> None:
        organisation_name = "A very long tenant organisation name " * 10

        out = InvestigationPackPdfService().build_pdf_bytes(_pack(), organisation_name=organisation_name)
        text = _pdf_text(out)

        assert organisation_name not in text
        assert "..." in text
        assert "PLANTEXPAND" in text
        assert "Page 1 of" in text

    def test_c1_honesty_notice_still_renders_on_a_branded_external_pack(self) -> None:
        out = InvestigationPackPdfService().build_pdf_bytes(_pack(redaction_log=[]), organisation_name="Plantexpand")
        text = _pdf_text(out)

        assert "No fields were redacted from the sections below." in text
        assert "Personal identities are redacted" not in text
        assert "Narrative text is reproduced as written" in text
        assert "PLANTEXPAND" in text

    def test_notice_is_latin1_safe_for_the_pdf_font(self) -> None:
        for audience in ("internal_customer", "external_customer"):
            notice = confidentiality_notice(audience, [{"redaction_type": "IDENTITY_REDACTION"}])

            assert notice.encode("latin-1").decode("latin-1") == notice


# ---------------------------------------------------------------------------
# Chronology figure (INV-C15)
# ---------------------------------------------------------------------------


def _flat(text: str) -> str:
    """Collapse the reader's line breaks so a wrapped sentence still matches."""
    return " ".join(text.split())


def _timeline_events() -> list[dict]:
    """Events in the shape `GET /investigations/{id}/timeline` serialises (INV-C9)."""
    return [
        {
            "id": -111,
            "event_type": "SOURCE_AUDIT",
            "new_value": "Incident raised",
            "actor_name": "Dana Reporter",
            "event_metadata": {"origin": "source", "source_label": "Incident \u00b7 create"},
            "created_at": "2026-05-01T08:00:00+00:00",
        },
        {
            "id": -212,
            "event_type": "SOURCE_RUNNING_SHEET",
            "new_value": "Brake wear noted on the nearside axle",
            "actor_name": "Dana Reporter",
            "event_metadata": {"origin": "source", "source_label": "Incident \u00b7 running sheet"},
            "created_at": "2026-05-04T09:30:00+00:00",
        },
        {
            "id": 7,
            "event_type": "STATUS_CHANGED",
            "new_value": "in_progress",
            "event_metadata": {"origin": "investigation"},
            "created_at": "2026-05-17T11:00:00+00:00",
        },
    ]


class TestPackChronology:
    def test_omitted_entirely_when_no_chronology_feed_is_supplied(self) -> None:
        # Today's route passes no feed. Printing "no events" would claim the
        # timeline had been consulted when it had not.
        text = _pdf_text(InvestigationPackPdfService().build_pdf_bytes(_pack(audience="internal_customer")))

        assert "Chronology" not in text

    def test_internal_pack_draws_the_figure_and_lists_the_entries(self) -> None:
        out = InvestigationPackPdfService().build_pdf_bytes(
            _pack(audience="internal_customer"),
            organisation_name="Plantexpand",
            timeline_events=_timeline_events(),
        )
        text = _pdf_text(out)

        assert out.startswith(b"%PDF-")
        assert "Chronology" in text
        assert "3 entries between 01 May 2026 and 17 May 2026" in text
        assert "2 from the source record, 1 from the investigation" in text
        assert "Source record" in text and "Investigation" in text
        assert "01 May 2026 08:00 UTC - Source record - Incident" in text
        assert "17 May 2026 11:00 UTC - Investigation - Status changed: in_progress" in text

    def test_figure_geometry_reaches_the_document(self) -> None:
        service = InvestigationPackPdfService()
        without = service.build_pdf_bytes(_pack(audience="internal_customer"))
        with_figure = service.build_pdf_bytes(
            _pack(audience="internal_customer"),
            timeline_events=_timeline_events(),
        )

        # Markers, lanes and axis are vector operations, not text: the rendered
        # document must grow by more than the words added to it.
        assert len(with_figure) > len(without) + 400

    def test_stored_chronology_is_declared_as_checksum_covered(self) -> None:
        pack = _pack(audience="internal_customer")
        pack["content"]["chronology"] = {"events": _timeline_events()}

        # Normalised because the caption wraps: a line break must not decide
        # whether the pack is judged to have told the truth.
        text = _flat(_pdf_text(InvestigationPackPdfService().build_pdf_bytes(pack)))

        assert "covered by the content checksum" in text
        assert "not covered by the content checksum" not in text

    def test_render_time_chronology_says_it_is_outside_the_checksum(self) -> None:
        text = _flat(
            _pdf_text(
                InvestigationPackPdfService().build_pdf_bytes(
                    _pack(audience="internal_customer"),
                    timeline_events=_timeline_events(),
                )
            )
        )

        assert "not part of the stored pack payload" in text
        assert "not covered by the content checksum" in text

    def test_a_bare_stored_list_is_accepted_as_well_as_an_events_mapping(self) -> None:
        pack = _pack(audience="internal_customer")
        pack["content"]["chronology"] = _timeline_events()

        text = _pdf_text(InvestigationPackPdfService().build_pdf_bytes(pack))

        assert "3 entries between 01 May 2026 and 17 May 2026" in text

    def test_feed_precedence_is_argument_then_payload_then_stored_content(self) -> None:
        pack = _pack(audience="internal_customer")
        pack["content"]["chronology"] = _timeline_events()
        pack["timeline_events"] = _timeline_events()[:2]

        assert chronology_feed(pack, pack["content"], _timeline_events()[:1])[1] == "render"
        assert len(chronology_feed(pack, pack["content"], _timeline_events()[:1])[0]) == 1
        assert len(chronology_feed(pack, pack["content"], None)[0]) == 2

        stored_only = _pack(audience="internal_customer")
        stored_only["content"]["chronology"] = _timeline_events()
        assert chronology_feed(stored_only, stored_only["content"], None)[1] == "pack"

    def test_no_feed_is_distinguishable_from_an_empty_feed(self) -> None:
        pack = _pack()

        assert chronology_feed(pack, pack["content"], None) == (None, "")
        assert chronology_feed(pack, pack["content"], []) == ([], "render")

    def test_a_non_list_feed_is_ignored_rather_than_rendered(self) -> None:
        pack = _pack(audience="internal_customer")
        pack["timeline_events"] = "nonsense"

        text = _pdf_text(InvestigationPackPdfService().build_pdf_bytes(pack, timeline_events={"items": []}))

        assert "Chronology" not in text

    def test_empty_feed_states_the_absence_without_a_figure(self) -> None:
        service = InvestigationPackPdfService()
        empty = service.build_pdf_bytes(_pack(audience="internal_customer"), timeline_events=[])
        text = _pdf_text(empty)

        assert "No chronology entries are recorded for this investigation." in text
        assert "Most recent entries" not in text
        assert "compiled from" not in text

    def test_external_pack_withholds_the_chronology_and_its_narrative(self) -> None:
        # Timeline entries are outside the pack redaction pass: an actor name and
        # a running-sheet narrative would be released unredacted.
        text = _pdf_text(
            InvestigationPackPdfService().build_pdf_bytes(
                _pack(audience="external_customer"),
                timeline_events=_timeline_events(),
            )
        )

        assert "The chronology is withheld from this pack." in text
        assert "Dana Reporter" not in text
        assert "Brake wear noted" not in text
        assert "Most recent entries" not in text

    def test_unknown_audience_fails_closed_like_the_confidentiality_notice(self) -> None:
        for audience in ("regulator", "", None):
            text = _pdf_text(
                InvestigationPackPdfService().build_pdf_bytes(
                    _pack(audience=audience),
                    timeline_events=_timeline_events(),
                )
            )

            assert "The chronology is withheld from this pack." in text
            assert "Brake wear noted" not in text

    def test_external_pack_with_an_empty_feed_does_not_claim_a_withholding(self) -> None:
        text = _pdf_text(
            InvestigationPackPdfService().build_pdf_bytes(_pack(audience="external_customer"), timeline_events=[])
        )

        assert "No chronology entries are recorded for this investigation." in text
        assert "The chronology is withheld from this pack." not in text

    def test_undated_entries_are_declared_not_silently_missing(self) -> None:
        events = _timeline_events() + [
            {"id": 8, "event_type": "COMMENT_ADDED", "created_at": None},
            {"id": 9, "event_type": "COMMENT_ADDED", "created_at": "whenever"},
        ]

        text = _pdf_text(
            InvestigationPackPdfService().build_pdf_bytes(
                _pack(audience="internal_customer"),
                timeline_events=events,
            )
        )

        assert "2 timeline entries carried no readable date" in text

    def test_a_long_chronology_renders_bounded_output(self) -> None:
        events = []
        for index in range(700):
            events.append(
                {
                    "id": index + 1,
                    "event_type": "SECTION_UPDATED",
                    "new_value": f"section_{index}",
                    "event_metadata": {"origin": "investigation"},
                    "created_at": f"2026-05-{(index % 28) + 1:02d}T08:{index % 60:02d}:00+00:00",
                }
            )

        out = InvestigationPackPdfService().build_pdf_bytes(
            _pack(audience="internal_customer"),
            timeline_events=events,
        )
        text = _pdf_text(out)

        assert out.startswith(b"%PDF-")
        assert "Most recent entries (12 of 500)" in text
        assert "200 earlier entries are not shown" in text

    def test_a_failing_figure_degrades_to_the_entry_list_instead_of_a_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*args: object, **kwargs: object) -> None:
            raise ValueError("fpdf blew up")

        monkeypatch.setattr(pack_pdf, "draw_chronology_figure", boom)

        out = InvestigationPackPdfService().build_pdf_bytes(
            _pack(audience="internal_customer"),
            timeline_events=_timeline_events(),
        )
        text = _pdf_text(out)

        assert out.startswith(b"%PDF-")
        assert "The chronology figure could not be drawn for this pack." in text
        assert "01 May 2026 08:00 UTC - Source record - Incident" in text

    def test_the_pack_renderer_still_reads_only_the_payload_it_was_given(self) -> None:
        # No database session, no timeline query: three supplied events are the
        # three the figure describes.
        text = _pdf_text(
            InvestigationPackPdfService().build_pdf_bytes(
                _pack(audience="internal_customer"),
                timeline_events=_timeline_events(),
            )
        )

        assert "3 entries" in text
        assert "Most recent entries (3 of 3)" in text

    def test_sections_evidence_and_integrity_still_render_around_the_figure(self) -> None:
        text = _pdf_text(
            InvestigationPackPdfService().build_pdf_bytes(
                _pack(audience="internal_customer"),
                organisation_name="Plantexpand Ltd",
                timeline_events=_timeline_events(),
            )
        )

        for expected in (
            "Report sections",
            "Brake maintenance interval exceeded",
            "Sections withheld from this pack",
            "Chronology",
            "Evidence schedule",
            "Dashcam still",
            "Redaction summary",
            "Pack integrity",
            "PLANTEXPAND",
        ):
            assert expected in text

    def test_non_latin1_chronology_text_does_not_break_the_render(self) -> None:
        events = _timeline_events()
        events[0]["event_metadata"]["source_label"] = "Incident \u2014 Ystrad Mynach"
        events[0]["new_value"] = "Driver said \u201cno warning\u201d \u2014 20\u00b0C"

        out = InvestigationPackPdfService().build_pdf_bytes(
            _pack(audience="internal_customer"),
            timeline_events=events,
        )

        assert out.startswith(b"%PDF-")


class TestInvestigationSectionRendering:
    def test_findings_whys_and_capa_render_as_lists_not_only_incident_details(self) -> None:
        pack = _pack(
            audience="internal_customer",
            content={
                "investigation_reference": "INV-2026-0007",
                "title": "Collision on the A1",
                "status": "completed",
                "level": "high",
                "sections": {
                    "section_1_details": {"incident_date": "2026-05-17"},
                    "findings": {"items": [{"body": "Guard was missing from the mill"}]},
                    "root-cause": {
                        "problem_statement": "Operator reached into the mill",
                        "whys": [
                            {
                                "level": 1,
                                "why": "Why was the guard off?",
                                "answer": "It had been removed for cleaning",
                            }
                        ],
                        "root_cause": "No permit for guard removal",
                        "contributing_factors": "Cleaning was treated as informal",
                    },
                    "capa": {
                        "items": [
                            {
                                "title": "Replace the guard",
                                "reference": "CAPA-2026-0042",
                                "why_level": 1,
                            }
                        ]
                    },
                },
            },
        )
        text = _flat(_pdf_text(InvestigationPackPdfService().build_pdf_bytes(pack)))

        assert "1. Guard was missing from the mill" in text
        assert "Why 1" in text
        assert "It had been removed for cleaning" in text
        assert "No permit for guard removal" in text
        assert "Cleaning was treated as informal" in text
        assert "CAPA-2026-0042 - Replace the guard (Why 1)" in text
        assert "Items:" not in text
        assert "Body: Guard" not in text

    def test_empty_investigation_lists_are_stated_empty(self) -> None:
        pack = _pack(
            content={
                "sections": {
                    "findings": {"items": []},
                    "root-cause": {
                        "problem_statement": "",
                        "whys": [],
                        "root_cause": "",
                        "contributing_factors": "",
                    },
                    "capa": {"items": []},
                }
            }
        )
        text = _pdf_text(InvestigationPackPdfService().build_pdf_bytes(pack))

        assert "No findings were recorded." in text
        assert "No 5-Whys were recorded." in text
        assert "No root-cause statement was recorded." in text
        assert "No contributing-factor text was recorded." in text
        assert "No CAPA actions were recorded." in text

    def test_omitted_findings_do_not_appear_in_the_pdf(self) -> None:
        pack = _pack(
            content={
                "sections": {
                    "section_1_details": {"location": "Mill floor"},
                    "root-cause": {"root_cause": "No permit", "whys": [], "contributing_factors": ""},
                },
                "omitted_sections": ["findings"],
            }
        )
        text = _pdf_text(InvestigationPackPdfService().build_pdf_bytes(pack))

        assert "Mill floor" in text
        assert "No permit" in text
        assert "Sections withheld from this pack" in text
        assert "Findings" in text
        assert "Guard was missing" not in text

    def test_external_pack_still_withholds_chronology_when_investigation_sections_render(self) -> None:
        pack = _pack(
            audience="external_customer",
            content={
                "sections": {
                    "findings": {"items": [{"body": "Guard was missing from the mill"}]},
                }
            },
        )
        text = _pdf_text(InvestigationPackPdfService().build_pdf_bytes(pack, timeline_events=_timeline_events()))

        assert "1. Guard was missing from the mill" in text
        assert "The chronology is withheld from this pack." in text
        assert "Dana Reporter" not in text
        assert "Brake wear noted" not in text


# ---------------------------------------------------------------------------
# ICAM contributing-factor diagram (INV-C16)
# ---------------------------------------------------------------------------

_CONTRIBUTING_TEXT = (
    "Organisational factors: No refresher training schedule (Budget withdrawn) [underlying cause]\n"
    "Individual and team actions: Operator reached into the running mill"
)


def _icam_factors(**overrides) -> dict:
    """The stored ICAM payload `serialize_rca_section` writes into the pack content."""
    payload = {
        "factors": [
            {
                "id": 4,
                "category": "organisational_factors",
                "cause": "No refresher training schedule",
                "sub_causes": ["Budget withdrawn"],
                "depth": "underlying",
            },
            {
                "id": 9,
                "category": "individual_team_actions",
                "cause": "Operator reached into the running mill",
                "sub_causes": [],
                "depth": None,
            },
        ],
        "unmapped_categories": [],
        "unpresentable": 0,
    }
    payload.update(overrides)
    return payload


def _rca_section(**overrides) -> dict:
    section = {
        "problem_statement": "Operator reached into the mill",
        "whys": [],
        "root_cause": "No permit for guard removal",
        "contributing_factors": _CONTRIBUTING_TEXT,
        "icam_factors": _icam_factors(),
    }
    section.update(overrides)
    return section


def _icam_pack(section: dict, *, audience: str = "internal_customer") -> dict:
    return _pack(audience=audience, content={"sections": {"root-cause": section}})


class TestPackIcamDiagram:
    def test_a_pack_with_no_icam_key_renders_exactly_as_before(self) -> None:
        # C13 and earlier packs never consulted the factors. Printing "none are
        # recorded" for one would claim something had been checked that was not.
        section = _rca_section()
        section.pop("icam_factors")

        text = _flat(_pdf_text(InvestigationPackPdfService().build_pdf_bytes(_icam_pack(section))))

        assert "ICAM contributing factors" not in text
        assert "No ICAM contributing factors are recorded" not in text
        assert "No refresher training schedule" in text  # the C13 text is untouched

    def test_stored_factors_render_the_heading_summary_bands_and_note(self) -> None:
        out = InvestigationPackPdfService().build_pdf_bytes(_icam_pack(_rca_section()), organisation_name="Plantexpand")
        text = _flat(_pdf_text(out))

        assert out.startswith(b"%PDF-")
        assert "ICAM contributing factors" in text
        assert "2 contributing factors recorded across the four ICAM categories, 1 with a recorded HSG245" in text
        for label in (
            "Organisational factors",
            "Task and environmental conditions",
            "Individual and team actions",
            "Absent or failed defences",
        ):
            assert label in text
        assert "No refresher training schedule (Budget withdrawn)" in text
        assert "groups the recorded contributing factors by ICAM category" in text

    def test_the_figure_geometry_reaches_the_document(self) -> None:
        service = InvestigationPackPdfService()
        section = _rca_section()
        without = service.build_pdf_bytes(_icam_pack({**section, "icam_factors": None}))
        with_figure = service.build_pdf_bytes(_icam_pack(section))

        # Bands, borders and depth markers are vector operations, not text: the
        # document must grow by more than the words added to it.
        assert len(with_figure) > len(without) + 400

    def test_an_empty_stored_diagram_says_so_and_invents_no_factor(self) -> None:
        section = _rca_section(
            contributing_factors="",
            icam_factors=_icam_factors(factors=[]),
        )

        text = _flat(_pdf_text(InvestigationPackPdfService().build_pdf_bytes(_icam_pack(section))))

        assert "No ICAM contributing factors are recorded for this investigation." in text
        assert "No contributing-factor text was recorded." in text
        assert "None recorded." not in text  # no empty bands were drawn
        assert "groups the recorded contributing factors" not in text

    def test_an_approved_omit_of_root_cause_withholds_the_diagram_with_the_section(self) -> None:
        # The generator drops a withheld section from content["sections"], so
        # there is nothing for the diagram to be drawn from — the withholding is
        # structural rather than a rule here that could be forgotten.
        pack = _pack(
            audience="internal_customer",
            content={
                "sections": {"section_1_details": {"location": "Mill floor"}},
                "omitted_sections": ["root-cause"],
            },
        )

        text = _flat(_pdf_text(InvestigationPackPdfService().build_pdf_bytes(pack)))

        assert "Sections withheld from this pack" in text
        assert "Root cause" in text  # named as withheld
        assert "ICAM contributing factors" not in text
        assert "No refresher training schedule" not in text
        assert "Organisational factors" not in text

    def test_a_failing_figure_degrades_to_the_factors_in_words_instead_of_a_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*args: object, **kwargs: object) -> None:
            raise ValueError("fpdf blew up")

        monkeypatch.setattr(pack_pdf, "draw_icam_factors_figure", boom)

        out = InvestigationPackPdfService().build_pdf_bytes(_icam_pack(_rca_section()))
        text = _flat(_pdf_text(out))

        assert out.startswith(b"%PDF-")
        assert "The ICAM contributing-factor diagram could not be drawn for this pack." in text
        assert "Organisational factors: No refresher training schedule (Budget withdrawn) [underlying cause]" in text
        assert "Individual and team actions: Operator reached into the running mill" in text
        assert "groups the recorded contributing factors" not in text

    def test_causes_outside_the_icam_four_are_counted_and_named_not_recategorised(self) -> None:
        section = _rca_section(
            icam_factors=_icam_factors(unmapped_categories=["machine", "mother_nature"], unpresentable=3)
        )

        text = _flat(_pdf_text(InvestigationPackPdfService().build_pdf_bytes(_icam_pack(section))))

        assert "3 stored causes could not be presented on the diagram." in text
        assert "That count includes causes stored under Machine, Mother nature" in text
        assert "counted here rather than recategorised" in text

    def test_a_single_unpresentable_cause_is_stated_in_the_singular(self) -> None:
        section = _rca_section(icam_factors=_icam_factors(unpresentable=1))

        text = _flat(_pdf_text(InvestigationPackPdfService().build_pdf_bytes(_icam_pack(section))))

        assert "1 stored cause could not be presented on the diagram." in text
        assert "That count includes causes stored under" not in text

    def test_a_long_diagram_is_bounded_and_says_what_it_did_not_draw(self) -> None:
        factors = [
            {
                "id": index + 1,
                "category": "organisational_factors",
                "cause": f"Contributing factor {index + 1}",
                "sub_causes": [],
                "depth": "root",
            }
            for index in range(60)
        ]
        section = _rca_section(icam_factors=_icam_factors(factors=factors))

        out = InvestigationPackPdfService().build_pdf_bytes(_icam_pack(section))
        text = _flat(_pdf_text(out))

        assert out.startswith(b"%PDF-")
        # The count stated is what is recorded, not what the figure fitted.
        assert "60 contributing factors recorded across the four ICAM categories; the diagram shows the first 24" in (
            text
        )
        assert "36 further factors are not shown in the diagram, which is capped at the first 24" in text
        assert "Contributing factor 24" in text
        assert "Contributing factor 25" not in text

    def test_an_unrecognised_stored_depth_is_not_drawn_as_a_recorded_one(self) -> None:
        section = _rca_section(
            icam_factors=_icam_factors(
                factors=[
                    {
                        "id": 1,
                        "category": "organisational_factors",
                        "cause": "Depth never classified",
                        "sub_causes": [],
                        "depth": "catastrophic",
                    }
                ]
            )
        )

        text = _flat(_pdf_text(InvestigationPackPdfService().build_pdf_bytes(_icam_pack(section))))

        assert "Depth never classified" in text
        assert "0 with a recorded HSG245 causal depth" in text
        assert "catastrophic" not in text

    def test_an_external_pack_draws_the_same_diagram_as_the_internal_one(self) -> None:
        # Unlike the chronology, nothing in the diagram is outside the redaction
        # pass: INV-C12 derives the contributing-factor text above it from these
        # same rows, so withholding the figure would hide nothing already
        # withheld while making the analysis look undone.
        service = InvestigationPackPdfService()
        internal = _flat(_pdf_text(service.build_pdf_bytes(_icam_pack(_rca_section()))))
        external = _flat(_pdf_text(service.build_pdf_bytes(_icam_pack(_rca_section(), audience="external_customer"))))

        for expected in ("ICAM contributing factors", "No refresher training schedule (Budget withdrawn)"):
            assert expected in internal
            assert expected in external
        assert "withheld" not in external.replace("Sections withheld from this pack", "")

    def test_a_malformed_stored_diagram_neither_raises_nor_invents(self) -> None:
        for stored in ("nonsense", 7, [], {}, {"factors": "nonsense"}, [None, 3]):
            out = InvestigationPackPdfService().build_pdf_bytes(_icam_pack(_rca_section(icam_factors=stored)))
            text = _flat(_pdf_text(out))

            assert out.startswith(b"%PDF-")
            assert "No ICAM contributing factors are recorded for this investigation." in text

    def test_non_latin1_factor_text_does_not_break_the_render(self) -> None:
        section = _rca_section(
            icam_factors=_icam_factors(
                factors=[
                    {
                        "id": 1,
                        "category": "task_environmental_conditions",
                        "cause": "Ystrad \u2014 Mynach yard at 20\u00b0C",
                        "sub_causes": ["Driver said \u201cno warning\u201d"],
                        "depth": "immediate",
                    }
                ]
            )
        )

        out = InvestigationPackPdfService().build_pdf_bytes(_icam_pack(section))

        # The degree sign is latin-1 and survives; the em dash and the curly
        # quotes are not, and are replaced rather than dropped or guessed.
        assert out.startswith(b"%PDF-")
        assert "Ystrad ? Mynach yard at 20\u00b0C (Driver said ?no warning?)" in _flat(_pdf_text(out))

    def test_the_diagram_does_not_displace_the_rest_of_the_pack(self) -> None:
        pack = _pack(
            audience="internal_customer",
            content={
                "sections": {
                    "section_1_details": {"location": "Mill floor"},
                    "findings": {"items": [{"body": "Guard was missing from the mill"}]},
                    "root-cause": _rca_section(),
                    "capa": {"items": [{"title": "Replace the guard", "reference": "CAPA-2026-0042"}]},
                },
                "omitted_sections": ["section_5_internal_commentary"],
            },
        )

        text = _flat(
            _pdf_text(
                InvestigationPackPdfService().build_pdf_bytes(
                    pack, organisation_name="Plantexpand Ltd", timeline_events=_timeline_events()
                )
            )
        )

        for expected in (
            "Report sections",
            "1. Guard was missing from the mill",
            "No permit for guard removal",
            "ICAM contributing factors",
            "CAPA-2026-0042 - Replace the guard",
            "Sections withheld from this pack",
            "Chronology",
            "Evidence schedule",
            "Redaction summary",
            "Pack integrity",
            "PLANTEXPAND",
        ):
            assert expected in text
