"""PX-255 — UVDB scoring policy: pending-empty sections excluded from qualification."""

from __future__ import annotations

from src.domain.services.uvdb_service import (
    SCORE_SOURCE_IMPORTED,
    build_section_title_index,
    match_protocol_section,
    normalise_section_score,
)
from src.domain.uvdb.protocol_b2_v118 import UVDB_B2_SECTIONS
from src.domain.uvdb.scoring_policy import (
    EXCLUSION_PENDING_PROTOCOL_PDF,
    apply_section_score_policy,
    apply_section_scores_policy,
    policy_adjusted_audit_percentage,
    qualification_percentage_from_sections,
    section_is_assessable,
)


class TestSectionAssessability:
    def test_loaded_section_with_questions_is_assessable(self):
        section = next(s for s in UVDB_B2_SECTIONS if s["number"] == "1")
        assert section_is_assessable(section) is True

    def test_pending_protocol_pdf_sections_are_not_assessable(self):
        pending = [s for s in UVDB_B2_SECTIONS if s.get("content_status") == "pending_protocol_pdf"]
        assert pending  # SSOT still has pending shells
        assert all(section_is_assessable(s) is False for s in pending)

    def test_missing_section_is_not_assessable(self):
        assert section_is_assessable(None) is False


class TestApplySectionScorePolicy:
    def test_pending_section_score_is_excluded_not_shown_as_pass(self):
        entry = {
            "label": "Section 4 Risk Assessment",
            "score": 14.0,
            "max_score": 15.0,
            "percentage": 93.3,
            "score_source": SCORE_SOURCE_IMPORTED,
        }
        protocol = next(s for s in UVDB_B2_SECTIONS if s["number"] == "4")
        result = apply_section_score_policy(
            entry,
            content_status="pending_protocol_pdf",
            mode="exclude",
            protocol_section=protocol,
        )
        assert result["assessed"] is False
        assert result["excluded_from_qualification"] is True
        assert result["exclusion_reason"] == EXCLUSION_PENDING_PROTOCOL_PDF
        assert result["percentage"] is None
        assert result["score"] is None

    def test_zero_mode_zeros_pending_section(self):
        entry = {"label": "Section 5", "score": 10.0, "max_score": 10.0, "percentage": 100.0}
        protocol = next(s for s in UVDB_B2_SECTIONS if s["number"] == "5")
        result = apply_section_score_policy(
            entry,
            content_status="pending_protocol_pdf",
            mode="zero",
            protocol_section=protocol,
        )
        assert result["percentage"] == 0.0
        assert result["score"] == 0.0
        assert result["excluded_from_qualification"] is True

    def test_loaded_section_passes_through(self):
        entry = {
            "label": "Section 1",
            "score": 18.0,
            "max_score": 21.0,
            "percentage": 85.7,
            "score_source": SCORE_SOURCE_IMPORTED,
        }
        protocol = next(s for s in UVDB_B2_SECTIONS if s["number"] == "1")
        result = apply_section_score_policy(
            entry,
            content_status="loaded",
            mode="exclude",
            protocol_section=protocol,
        )
        assert result["assessed"] is True
        assert result["excluded_from_qualification"] is False
        assert result["percentage"] == 85.7


class TestQualificationAverage:
    def test_fabricated_high_average_collapses_when_pending_excluded(self):
        """Classic PX-255: S1–S2 real + S3–S11 imported near-100% → headline ~99%.

        After exclusion, only loaded sections contribute.
        """
        sections_map = {
            "1": {"percentage": 90.0, "score_source": SCORE_SOURCE_IMPORTED},
            "2": {"percentage": 88.0, "score_source": SCORE_SOURCE_IMPORTED},
            "3": {"percentage": 93.0, "score_source": SCORE_SOURCE_IMPORTED},
            "4": {"percentage": 100.0, "score_source": SCORE_SOURCE_IMPORTED},
            "5": {"percentage": 100.0, "score_source": SCORE_SOURCE_IMPORTED},
            "6": {"percentage": 100.0, "score_source": SCORE_SOURCE_IMPORTED},
            "7": {"percentage": 100.0, "score_source": SCORE_SOURCE_IMPORTED},
            "8": {"percentage": 100.0, "score_source": SCORE_SOURCE_IMPORTED},
            "9": {"percentage": 97.0, "score_source": SCORE_SOURCE_IMPORTED},
            "10": {"percentage": 100.0, "score_source": SCORE_SOURCE_IMPORTED},
            "11": {"percentage": 100.0, "score_source": SCORE_SOURCE_IMPORTED},
        }
        naive = round(sum(e["percentage"] for e in sections_map.values()) / len(sections_map), 1)
        assert naive >= 97.0  # the fabricated headline

        adjusted_map = apply_section_scores_policy(
            sections_map,
            protocol_sections=UVDB_B2_SECTIONS,
            mode="exclude",
        )
        qualification = qualification_percentage_from_sections(adjusted_map)
        assert qualification == 89.0  # mean of 90 and 88 only
        assert adjusted_map["3"]["excluded_from_qualification"] is True
        assert adjusted_map["1"]["excluded_from_qualification"] is False

    def test_all_pending_yields_no_qualification_score(self):
        sections_map = {
            "3": {"percentage": 100.0},
            "4": {"percentage": 100.0},
        }
        adjusted = apply_section_scores_policy(
            sections_map,
            protocol_sections=UVDB_B2_SECTIONS,
            mode="exclude",
        )
        assert qualification_percentage_from_sections(adjusted) is None


class TestPolicyAdjustedAuditPercentage:
    def test_recomputes_from_loaded_sections_only(self):
        raw = {
            "sections": [
                {"label": "Section 1 System Assurance", "score": 18, "max_score": 21},
                {"label": "Section 4 Risk Assessment", "score": 14, "max_score": 15},
            ]
        }
        title_index = build_section_title_index(UVDB_B2_SECTIONS)
        adjusted, meta = policy_adjusted_audit_percentage(
            stored_percentage=99.0,
            section_scores_raw=raw,
            protocol_sections=UVDB_B2_SECTIONS,
            match_section=match_protocol_section,
            normalise_entry=lambda entry: normalise_section_score(
                entry, audit_reference="UVDB-1", score_source=SCORE_SOURCE_IMPORTED
            ),
            title_index=title_index,
        )
        assert meta["policy_applied"] is True
        assert "4" in meta["excluded_section_numbers"]
        assert "1" in meta["included_section_numbers"]
        # Section 1 only: 18/21 ≈ 85.7
        assert adjusted == 85.7

    def test_falls_back_to_stored_when_no_breakdown(self):
        adjusted, meta = policy_adjusted_audit_percentage(
            stored_percentage=91.0,
            section_scores_raw=None,
            protocol_sections=UVDB_B2_SECTIONS,
            match_section=match_protocol_section,
            normalise_entry=lambda entry: normalise_section_score(entry, audit_reference=None, score_source=None),
        )
        assert adjusted == 91.0
        assert meta["fallback_to_stored"] is True
