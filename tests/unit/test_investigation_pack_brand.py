"""Brand kit for investigation packs — letterhead is not the tenant row."""

from __future__ import annotations

import io

import pytest

from src.domain.services import investigation_pack_brand as brand
from src.domain.services.investigation_pack_pdf import InvestigationPackPdfService
from src.domain.services.investigation_pack_pdf_writer import UnknownBlockError, write_block


def _pack(**overrides):
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
            "sections": {"section_1_details": {"reference_number": "INC-2026-0001"}},
        },
        "redaction_log": [],
        "included_assets": [],
    }
    pack.update(overrides)
    return pack


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(data)).pages)


class TestBrandAssets:
    def test_inter_weights_lockup_and_ofl_resolve(self) -> None:
        brand.resolve_typeface()
        for weight in ("regular", "medium", "semibold", "bold"):
            assert brand.font_path(weight).is_file()
        assert brand.lockup_path().is_file()
        assert brand.reverse_lockup_path().is_file()
        assert brand.ofl_path().is_file()
        assert "SIL OPEN FONT LICENSE" in brand.ofl_path().read_text()

    def test_palette_is_the_kit_not_tailwind_blue(self) -> None:
        assert brand.CRIMSON == (186, 55, 55)
        assert brand.JET_GREY == (51, 48, 48)
        assert brand.LIME == (190, 218, 65)
        assert brand.DODGER == (40, 104, 206)
        assert brand.PLATINUM == (235, 232, 232)
        assert brand.CRIMSON != brand.TAILWIND_BLUE
        assert brand.JET_GREY != brand.TAILWIND_BLUE

    def test_legal_identity_is_plantexpand_ltd(self) -> None:
        line = brand.legal_footer_line()
        assert "Plantexpand Ltd" in line
        assert "Unit 7 Buckingham Square" in line
        assert "SS11 8YQ" in line
        assert "01268 204782" in line
        assert "PLANTEXPAND.COM" in line

    def test_missing_reverse_lockup_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(brand, "_REVERSE_LOCKUP_FILE", "missing-reverse.png")
        with pytest.raises(brand.BrandAssetError, match="reverse lockup"):
            brand.reverse_lockup_path()

    def test_cover_band_carries_the_reverse_lockup_and_the_web(self) -> None:
        from pypdf import PdfReader

        out = InvestigationPackPdfService().build_pdf_bytes(_pack())
        reader = PdfReader(io.BytesIO(out))
        cover = reader.pages[0]
        assert len(cover.images) >= 2
        text = (cover.extract_text() or "").upper()
        assert "PLANTEXPAND.COM" in text
        assert "CONFIDENTIAL" in text

    def test_missing_lockup_fails_closed_without_helvetica(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(brand, "_LOCKUP_FILE", "missing-lockup.png")
        with pytest.raises(brand.BrandAssetError, match="lockup"):
            brand.lockup_path()

    def test_uk_punctuation_is_in_the_bundled_cmap(self) -> None:
        cmap = brand.covered_codepoints()
        for ch in ("\u2014", "\u2013", "\u201c", "\u201d", "\u00b0", "\u00a3", "\u2026", "\u2022"):
            assert ord(ch) in cmap, ch

    def test_uncovered_glyph_becomes_visible_question_mark(self) -> None:
        # A codepoint Inter does not cover must not vanish.
        out = brand.text_safe("ok \U0001f525 ok")
        assert "ok" in out
        assert "\U0001f525" not in out
        assert "?" in out


class TestLetterheadLock:
    def test_tenant_name_and_tailwind_blue_do_not_become_the_letterhead(self) -> None:
        out = InvestigationPackPdfService().build_pdf_bytes(
            _pack(),
            organisation_name="Default Organisation",
            primary_color="#3B82F6",
        )
        text = _pdf_text(out)
        assert "Default Organisation" not in text
        assert "Plantexpand Ltd" in text
        assert "UNCONTROLLED WHEN PRINTED" in text
        assert "UNIT 7 BUCKINGHAM SQUARE" in text.upper()
        assert b"Helvetica" not in out
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(out))
        first = reader.pages[0]
        fonts = first["/Resources"]["/Font"]
        names = []
        for _key, value in fonts.items():
            font = value.get_object()
            names.append(str(font.get("/BaseFont") or ""))
            assert str(font.get("/Subtype") or "") in {"/Type0", "/TrueType", "/Type1"}
        assert any("Inter" in name for name in names)
        assert first.images, "cover must embed the lockup"

    def test_cover_is_unnumbered_and_body_pages_start_at_one(self) -> None:
        out = InvestigationPackPdfService().build_pdf_bytes(_pack())
        text = _pdf_text(out)
        assert "INVESTIGATION REPORT" in text
        assert "Report" in text
        assert "CONTENTS" in text
        assert "PAGE 1 OF" in text
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(out))
        pages = len(reader.pages)
        cover = reader.pages[0].extract_text() or ""
        assert "PAGE 1" not in cover
        assert "PAGE 1 OF" not in cover
        body_pages = pages - 1
        assert f"PAGE 1 OF {body_pages}" in text
        body = reader.pages[1].extract_text() or ""
        assert "CONTENTS" in body.upper()
        assert "INVESTIGATION REPORT" in text
        assert "UNCONTROLLED WHEN PRINTED" in text
        assert "EXTERNAL CUSTOMER PACK" in text.upper() or "External customer pack" in text

    def test_unknown_block_raises_rather_than_skipping(self) -> None:
        class Mystery:
            pass

        with pytest.raises(UnknownBlockError):
            write_block(None, Mystery())  # type: ignore[arg-type]
