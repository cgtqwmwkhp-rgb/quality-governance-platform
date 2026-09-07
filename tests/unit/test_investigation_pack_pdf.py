"""Unit tests for the investigation customer pack PDF renderer (PX-143)."""

from __future__ import annotations

import builtins
import io
import re

import pytest

from src.domain.services import investigation_pack_pdf as pack_pdf
from src.domain.services.investigation_pack_pdf import (
    InvestigationPackPdfService,
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
