"""Unit tests for UVDB B2 protocol SSOT module."""

from __future__ import annotations

from src.domain.uvdb.protocol_b2_v118 import (
    PENDING_SECTION_NUMBERS,
    PROTOCOL_VERSION,
    TOTAL_SECTIONS,
    UVDB_B2_SECTIONS,
    build_content_coverage,
)


def test_protocol_ssot_has_fifteen_sections_in_order() -> None:
    numbers = [section["number"] for section in UVDB_B2_SECTIONS]
    assert numbers == [str(i) for i in range(1, TOTAL_SECTIONS + 1)]


def test_protocol_ssot_loaded_sections_keep_question_text() -> None:
    section_one = next(section for section in UVDB_B2_SECTIONS if section["number"] == "1")
    assert section_one["content_status"] == "loaded"
    assert section_one["questions"][0]["number"] == "1.1"
    assert "Quality Management Systems" in section_one["questions"][0]["text"]


def test_protocol_ssot_pending_sections_are_honest_shells() -> None:
    pending = [section for section in UVDB_B2_SECTIONS if section["number"] in PENDING_SECTION_NUMBERS]
    assert len(pending) == 9
    assert all(section["content_status"] == "pending_protocol_pdf" for section in pending)
    assert all(section["title_provisional"] is True for section in pending)
    assert all(section["questions"] == [] for section in pending)


def test_build_content_coverage_reports_partial_load() -> None:
    coverage = build_content_coverage()

    assert coverage["protocol_version"] == PROTOCOL_VERSION
    assert coverage["status"] == "partial"
    assert coverage["total_sections"] == 15
    assert coverage["loaded_sections"] == ["1", "2", "12", "13", "14", "15"]
    assert coverage["pending_sections"] == list(PENDING_SECTION_NUMBERS)
    assert coverage["loaded_question_count"] > 0
    assert coverage["pending_question_count"] == 0
