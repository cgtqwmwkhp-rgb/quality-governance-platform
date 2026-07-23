"""Unit tests for investigation → case lessons promote helpers."""

from src.domain.services.lessons_learnt_promote import extract_lessons_text


def test_extract_from_section_7_lessons():
    data = {"sections": {"section_7_lessons": {"content": "  Check PPE before lift  "}}}
    assert extract_lessons_text(data) == "Check PPE before lift"


def test_extract_falls_back_to_conclusion():
    assert extract_lessons_text({"conclusion": "Brief the crew"}) == "Brief the crew"


def test_extract_empty():
    assert extract_lessons_text(None) is None
    assert extract_lessons_text({}) is None
