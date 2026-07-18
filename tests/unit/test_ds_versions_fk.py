"""DS-4/DS-5 — filename version hints, library metadata edit, control↔library FK."""

from __future__ import annotations

import pytest

from src.domain.exceptions import BadRequestError
from src.domain.services.document_version_service import (
    assert_library_metadata_editable,
    parse_filename_version_hint,
    parse_version,
)
from src.domain.services.gkb_control_library_link import matching_fields_for


def test_parse_filename_version_hint_advisory_only():
    hint = parse_filename_version_hint("ISO9001_Policy_v2.1_final.pdf")
    assert hint is not None
    assert hint.label == "2.1"
    assert parse_filename_version_hint("no-version-here.pdf") is None


def test_filename_hint_does_not_override_parse_version():
    hint = parse_filename_version_hint("doc_v3.2.pdf")
    assert hint and hint.label == "3.2"
    assert parse_version("1.0").label == "1.0"


def test_library_metadata_editable_on_draft_not_published():
    assert_library_metadata_editable("draft")
    assert_library_metadata_editable("under_revision")
    with pytest.raises(BadRequestError, match="read-only"):
        assert_library_metadata_editable("published")


def test_matching_fields_for_title_and_reference():
    from types import SimpleNamespace

    controlled = SimpleNamespace(title="PPE Procedure", document_number="PROC-11")
    library = SimpleNamespace(title="PPE Procedure", reference_number="PROC-11")
    assert matching_fields_for(controlled, library) == ["title", "reference_number"]
