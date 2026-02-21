"""Unit tests for DocumentAIService - can run standalone."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.domain.services.document_ai_service import DocumentAIService, DocumentAnalysis, DocumentChunk  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def svc():
    with patch("src.domain.services.document_ai_service.settings"):
        return DocumentAIService()


SAMPLE_CONTENT = (
    "This is a safety policy document for the organization. "
    "All employees must wear PPE in designated areas. "
    "Inspections are conducted quarterly by the safety team."
)

SECTIONED_CONTENT = """# Introduction
This document describes the safety policy.

# Scope
Applies to all employees and contractors.

# Responsibilities
The safety officer is responsible for enforcement.
"""


# ---------------------------------------------------------------------------
# _fallback_analysis tests
# ---------------------------------------------------------------------------


def test_fallback_returns_document_analysis(svc):
    """Fallback analysis returns a DocumentAnalysis dataclass."""
    result = svc._fallback_analysis(SAMPLE_CONTENT, "safety_policy.pdf")
    assert isinstance(result, DocumentAnalysis)
    print("✓ Fallback returns DocumentAnalysis")


def test_fallback_detects_policy_type(svc):
    """Filename containing 'policy' sets document_type to 'policy'."""
    result = svc._fallback_analysis(SAMPLE_CONTENT, "safety_policy.pdf")
    assert result.document_type == "policy"
    print("✓ 'policy' detected from filename")


def test_fallback_detects_procedure_type(svc):
    """Filename containing 'procedure' sets document_type to 'procedure'."""
    result = svc._fallback_analysis(SAMPLE_CONTENT, "maintenance_procedure.docx")
    assert result.document_type == "procedure"
    print("✓ 'procedure' detected from filename")


def test_fallback_detects_sop_type(svc):
    """Filename containing 'sop' sets document_type to 'sop'."""
    result = svc._fallback_analysis(SAMPLE_CONTENT, "SOP-cleaning.pdf")
    assert result.document_type == "sop"
    print("✓ 'sop' detected from filename")


def test_fallback_unknown_type(svc):
    """Unrecognized filename defaults to 'other'."""
    result = svc._fallback_analysis(SAMPLE_CONTENT, "random_notes.txt")
    assert result.document_type == "other"
    print("✓ Unknown filename = 'other'")


def test_fallback_low_confidence(svc):
    """Fallback analysis sets confidence to 0.3."""
    result = svc._fallback_analysis(SAMPLE_CONTENT, "doc.pdf")
    assert result.confidence == 0.3
    print("✓ Fallback confidence is 0.3")


def test_fallback_extracts_keywords(svc):
    """Fallback extracts keywords from content by word frequency."""
    result = svc._fallback_analysis(SAMPLE_CONTENT, "doc.pdf")
    assert len(result.keywords) > 0
    assert len(result.keywords) <= 10
    print(f"✓ Extracted {len(result.keywords)} keywords")


def test_fallback_detects_tables(svc):
    """Content with '|' triggers has_tables=True."""
    content = "Header | Value\n---|---\nRow1 | Data"
    result = svc._fallback_analysis(content, "table_doc.pdf")
    assert result.has_tables is True
    print("✓ Table detection works")


def test_fallback_summary_truncation(svc):
    """Summary is first 200 chars + ellipsis."""
    long_content = "A" * 500
    result = svc._fallback_analysis(long_content, "doc.pdf")
    assert result.summary.endswith("...")
    assert len(result.summary) <= 204  # 200 chars + "..."
    print("✓ Summary truncated correctly")


def test_fallback_entities_structure(svc):
    """Fallback entities has the expected empty lists."""
    result = svc._fallback_analysis(SAMPLE_CONTENT, "doc.pdf")
    assert "contacts" in result.entities
    assert "assets" in result.entities
    assert "procedures" in result.entities
    assert "standards" in result.entities
    print("✓ Entity structure correct")


# ---------------------------------------------------------------------------
# _split_by_sections tests
# ---------------------------------------------------------------------------


def test_split_sections_with_headings(svc):
    """Document with markdown headings splits into multiple sections."""
    sections = svc._split_by_sections(SECTIONED_CONTENT)
    assert len(sections) >= 3
    headings = [s[0] for s in sections]
    assert "Introduction" in headings
    assert "Scope" in headings
    assert "Responsibilities" in headings
    print(f"✓ Split into {len(sections)} sections")


def test_split_sections_no_headings(svc):
    """Document without headings returns single section with None heading."""
    sections = svc._split_by_sections("Just a plain paragraph of text.")
    assert len(sections) == 1
    assert sections[0][0] is None
    print("✓ No-heading document returns single section")


# ---------------------------------------------------------------------------
# _split_by_size tests
# ---------------------------------------------------------------------------


def test_split_by_size_respects_max(svc):
    """Each chunk is at most max_size characters (on sentence boundaries)."""
    content = ". ".join([f"Sentence number {i}" for i in range(50)]) + "."
    chunks = svc._split_by_size(content, max_size=100, overlap=0)
    for chunk in chunks:
        assert len(chunk) <= 120  # Allow small overshoot from sentence boundary
    assert len(chunks) > 1
    print(f"✓ Split into {len(chunks)} size-bounded chunks")


def test_split_by_size_single_chunk(svc):
    """Short content stays in one chunk."""
    chunks = svc._split_by_size("Short text.", max_size=1000, overlap=0)
    assert len(chunks) == 1
    print("✓ Short content = 1 chunk")


# ---------------------------------------------------------------------------
# generate_chunks tests (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_chunks_with_sections(svc):
    """Sectioned document produces multiple chunks with headings."""
    chunks = await svc.generate_chunks(SECTIONED_CONTENT, max_chunk_size=500)
    assert len(chunks) >= 3
    assert all(isinstance(c, DocumentChunk) for c in chunks)
    assert chunks[0].index == 0
    print(f"✓ Generated {len(chunks)} chunks from sectioned doc")


@pytest.mark.asyncio
async def test_generate_chunks_plain_text(svc):
    """Plain text document falls back to size-based splitting."""
    content = ". ".join([f"Sentence {i} with some words" for i in range(100)]) + "."
    chunks = await svc.generate_chunks(content, max_chunk_size=200)
    assert len(chunks) > 1
    assert all(c.heading is None for c in chunks)
    print(f"✓ Generated {len(chunks)} chunks from plain text")


@pytest.mark.asyncio
async def test_generate_chunks_token_count(svc):
    """Each chunk has a positive token_count based on word splitting."""
    chunks = await svc.generate_chunks(SECTIONED_CONTENT, max_chunk_size=500)
    for chunk in chunks:
        assert chunk.token_count > 0
    print("✓ All chunks have positive token_count")


@pytest.mark.asyncio
async def test_generate_chunks_char_positions(svc):
    """char_start < char_end for every chunk."""
    chunks = await svc.generate_chunks(SECTIONED_CONTENT, max_chunk_size=500)
    for chunk in chunks:
        assert chunk.char_start < chunk.char_end
    print("✓ char_start < char_end for all chunks")


# ---------------------------------------------------------------------------
# analyze_document fallback tests (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_document_no_api_key(svc):
    """Without API key, analyze_document uses fallback analysis."""
    svc.api_key = None
    result = await svc.analyze_document(SAMPLE_CONTENT, "policy.pdf", "application/pdf")
    assert isinstance(result, DocumentAnalysis)
    assert result.confidence == 0.3
    print("✓ No API key falls back gracefully")


if __name__ == "__main__":
    import asyncio

    print("=" * 60)
    print("DOCUMENT AI SERVICE TESTS")
    print("=" * 60)
    print()

    with patch("src.domain.services.document_ai_service.settings"):
        s = DocumentAIService()

    test_fallback_returns_document_analysis(s)
    test_fallback_detects_policy_type(s)
    test_fallback_detects_procedure_type(s)
    test_fallback_detects_sop_type(s)
    test_fallback_unknown_type(s)
    test_fallback_low_confidence(s)
    test_fallback_extracts_keywords(s)
    test_fallback_detects_tables(s)
    test_fallback_summary_truncation(s)
    test_fallback_entities_structure(s)
    print()
    test_split_sections_with_headings(s)
    test_split_sections_no_headings(s)
    print()
    test_split_by_size_respects_max(s)
    test_split_by_size_single_chunk(s)
    print()
    asyncio.run(test_generate_chunks_with_sections(s))
    asyncio.run(test_generate_chunks_plain_text(s))
    asyncio.run(test_generate_chunks_token_count(s))
    asyncio.run(test_generate_chunks_char_positions(s))
    print()
    asyncio.run(test_analyze_document_no_api_key(s))

    print()
    print("=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)
