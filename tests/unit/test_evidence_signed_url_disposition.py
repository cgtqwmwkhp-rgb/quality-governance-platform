"""Unit tests for evidence signed-URL Content-Disposition resolution."""

import pytest

from src.api.utils.evidence_disposition import resolve_evidence_signed_url_disposition


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
