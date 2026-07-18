"""Unit tests for document version control service (CUJ create→revise→publish)."""

from __future__ import annotations

import pytest

from src.domain.exceptions import BadRequestError
from src.domain.services.document_version_service import (
    assert_document_metadata_editable,
    assert_version_mutable,
    next_version,
    parse_version,
    version_is_immutable,
)


def test_parse_and_next_version_major_minor():
    tip = parse_version("1.0")
    assert tip.label == "1.0"
    assert next_version(tip, is_major=False).label == "1.1"
    assert next_version(tip, is_major=True).label == "2.0"


def test_invalid_version_falls_back_to_1_0():
    assert parse_version("not-a-version").label == "1.0"
    assert parse_version(None).label == "1.0"


def test_published_versions_are_immutable():
    assert version_is_immutable("published") is True
    assert version_is_immutable("superseded") is True
    assert version_is_immutable("draft") is False
    assert version_is_immutable("draft", is_immutable=True) is True

    with pytest.raises(BadRequestError, match="immutable"):
        assert_version_mutable("published")

    assert_version_mutable("draft")


def test_published_document_metadata_is_read_only():
    with pytest.raises(BadRequestError, match="read-only"):
        assert_document_metadata_editable("published")
    with pytest.raises(BadRequestError, match="read-only"):
        assert_document_metadata_editable("obsolete")
    assert_document_metadata_editable("draft")
    assert_document_metadata_editable("under_revision")


def test_parse_filename_version_hint():
    from src.domain.services.document_version_service import parse_filename_version_hint

    assert parse_filename_version_hint("Manual_v2.1.pdf").label == "2.1"
    assert parse_filename_version_hint("plain.pdf") is None


def test_initial_controlled_version_matches_tip_honesty():
    from src.domain.services.document_version_service import document_version_service

    version = document_version_service.build_initial_controlled_version(
        tenant_id=7,
        document_id=42,
        author_name="Ada",
        created_by_id=9,
    )
    assert version.version_number == "1.0"
    assert version.major_version == 1
    assert version.minor_version == 0
    assert version.status == "draft"
    assert version.is_immutable is False
    assert version.change_type == "new"
