"""Unit tests for the investigation customer pack PDF renderer (PX-143)."""

from __future__ import annotations

import builtins
import re

import pytest

from src.domain.services.investigation_pack_pdf import (
    InvestigationPackPdfService,
    format_field_value,
    humanise_key,
    summarise_redactions,
)


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
