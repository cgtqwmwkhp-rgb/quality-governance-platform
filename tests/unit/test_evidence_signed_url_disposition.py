"""Unit tests for evidence Content-Disposition resolution and header building."""

import pytest

from src.api.utils.evidence_disposition import (
    build_evidence_content_disposition,
    resolve_evidence_signed_url_disposition,
)


@pytest.mark.parametrize(
    ("requested", "content_type", "expected"),
    [
        ("inline", "image/jpeg", "inline"),
        ("inline", "image/png", "inline"),
        ("inline", "image/webp; charset=binary", "inline"),
        ("inline", "application/pdf", "inline"),
        ("inline", "application/pdf; charset=utf-8", "inline"),
        ("inline", "video/mp4", "inline"),
        ("inline", "video/webm", "inline"),
        ("inline", "audio/mpeg", "inline"),
        ("inline", "audio/wav", "inline"),
        ("attachment", "application/pdf", "attachment"),
        ("attachment", "image/jpeg", "attachment"),
        ("inline", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "attachment"),
        ("inline", "application/msword", "attachment"),
        ("inline", "application/vnd.ms-excel", "attachment"),
        ("inline", "application/octet-stream", "attachment"),
        ("inline", "text/html", "attachment"),
        ("inline", "text/plain", "attachment"),
        ("inline", "", "attachment"),
        ("inline", None, "attachment"),
        ("inline", "   ", "attachment"),
        ("inline", "APPLICATION/PDF", "inline"),
        ("inline", "Image/JPEG", "inline"),
    ],
)
def test_resolve_evidence_signed_url_disposition(requested, content_type, expected):
    assert resolve_evidence_signed_url_disposition(requested, content_type) == expected


def test_requested_unknown_falls_back_to_attachment():
    assert resolve_evidence_signed_url_disposition("something-else", "application/pdf") == "attachment"


# ---------------------------------------------------------------------------
# Header building — only the byte-serving endpoint puts this in a real header
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("disposition", "filename", "expected"),
    [
        ("inline", "scene.png", 'inline; filename="scene.png"'),
        ("attachment", "report.pdf", 'attachment; filename="report.pdf"'),
        ("inline", "a photo.jpg", 'inline; filename="a photo.jpg"'),
    ],
)
def test_plain_ascii_filenames_are_passed_through_unchanged(disposition, filename, expected):
    assert build_evidence_content_disposition(disposition, filename) == expected


@pytest.mark.parametrize("filename", [None, "", "   "])
def test_a_missing_filename_becomes_download(filename):
    assert build_evidence_content_disposition("attachment", filename) == 'attachment; filename="download"'


def test_non_latin1_filename_is_sanitised_and_carried_in_filename_star():
    header = build_evidence_content_disposition("inline", "café.png")

    assert header == "inline; filename=\"caf_.png\"; filename*=UTF-8''caf%C3%A9.png"
    header.encode("latin-1")  # Starlette encodes response headers as latin-1


def test_a_quote_cannot_close_the_filename_parameter():
    header = build_evidence_content_disposition("attachment", 'evil".txt')

    assert header.count('"') == 2
    assert header.startswith('attachment; filename="evil_.txt"')


def test_crlf_cannot_be_injected_into_the_header():
    header = build_evidence_content_disposition("attachment", "a\r\nX-Injected: 1.txt")

    assert "\r" not in header and "\n" not in header


def test_a_filename_of_only_unsafe_characters_still_produces_a_parameter():
    header = build_evidence_content_disposition("attachment", "\x00\x01")

    assert header.startswith('attachment; filename="__"')
