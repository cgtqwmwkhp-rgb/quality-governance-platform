"""Governance Library Wave W1 — filing rules + lifecycle alignment tests."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import BadRequestError, NotFoundError, StateTransitionError, ValidationError
from src.domain.models.document import Document
from src.domain.models.document_library import DocumentCategory
from src.domain.models.enums import DocumentStatus
from src.domain.services.document_library_filing_service import (
    assert_library_read_access,
    compute_retention_until,
    filing_defaults_for_category,
    is_statutory_taxonomy_id,
    normalize_title,
    titles_are_similar,
)
from src.domain.services.document_library_lifecycle_service import (
    approve_document,
    reject_review,
    submit_for_review,
)


def _category(*, taxonomy_id: str = "04.04", default_access: str = "managers") -> DocumentCategory:
    return DocumentCategory(
        taxonomy_id=taxonomy_id,
        parent_id=None,
        level=2,
        sort_order=1,
        name="Fire Risk Assessments",
        slug="fire-risk-assessments",
        ref_prefix="PEL-FIR-01",
        default_access=default_access,
        retention_rule="Current + superseded 6 years",
        active=True,
    )


def test_statutory_defaults_for_sections_03_and_04():
    assert is_statutory_taxonomy_id("03.01") is True
    assert is_statutory_taxonomy_id("04.04") is True
    assert is_statutory_taxonomy_id("02.08") is False

    statutory = filing_defaults_for_category(_category(taxonomy_id="03.02"))
    assert statutory.is_statutory is True
    assert statutory.access_level == "managers"

    non_statutory = filing_defaults_for_category(_category(taxonomy_id="02.01", default_access="all_staff"))
    assert non_statutory.is_statutory is False
    assert non_statutory.access_level == "all_staff"


def test_similar_title_detection():
    assert titles_are_similar("Fire Risk Assessment 2026", "fire risk assessment 2026") is True
    assert titles_are_similar("Fire Risk Assessment", "Fire Risk Assessment - Site A") is True
    assert titles_are_similar("LOLER Certificate", "Near Miss Report") is False


def test_retention_until_parses_years_from_pick_list():
    category = _category()
    approved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    until = compute_retention_until(category, approved_at)
    assert until is not None
    assert until.year in {2031, 2032}


def test_acl_returns_404_not_403_for_restricted():
    document = SimpleNamespace(access_level="restricted")
    user = SimpleNamespace(is_superuser=False, has_permission=lambda _perm: False)
    with pytest.raises(NotFoundError):
        assert_library_read_access(document, user)

    manager_user = SimpleNamespace(
        is_superuser=False,
        has_permission=lambda perm: perm in {"document:update", "admin:manage"},
    )
    assert_library_read_access(SimpleNamespace(access_level="managers"), manager_user)


@pytest.mark.asyncio
async def test_submit_draft_to_under_review():
    document = Document(
        id=1,
        tenant_id=1,
        title="Test",
        file_name="a.pdf",
        file_type="pdf",
        file_size=1,
        file_path="x",
        category_id=10,
        status=DocumentStatus.DRAFT,
    )
    db = SimpleNamespace(flush=AsyncMock())
    updated = await submit_for_review(db, document)
    assert updated.status == DocumentStatus.UNDER_REVIEW


@pytest.mark.asyncio
async def test_submit_rejects_non_draft():
    document = SimpleNamespace(category_id=1, status=DocumentStatus.APPROVED)
    db = SimpleNamespace(flush=AsyncMock())
    with pytest.raises(StateTransitionError):
        await submit_for_review(db, document)


@pytest.mark.asyncio
async def test_approve_rejects_self_approval():
    document = SimpleNamespace(
        id=1,
        tenant_id=1,
        status=DocumentStatus.UNDER_REVIEW,
        created_by_id=5,
        category_id=None,
        pel_doc_ref=None,
        version="1.0",
        file_name="a.pdf",
        file_path="x",
        file_size=1,
    )
    version = SimpleNamespace(
        id=9,
        status="draft",
        is_immutable=False,
        version_number="1.0",
        file_name="a.pdf",
        file_path="x",
        file_size=1,
    )

    async def scalar(_stmt):
        return version

    db = SimpleNamespace(
        scalar=scalar,
        execute=AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))),
        get=AsyncMock(return_value=None),
        flush=AsyncMock(),
    )

    with pytest.raises(BadRequestError, match="Self-approval"):
        await approve_document(db, document, approved_by_id=5)


@pytest.mark.asyncio
async def test_reject_returns_to_draft():
    document = SimpleNamespace(
        status=DocumentStatus.UNDER_REVIEW,
        reviewed_by_id=None,
        reviewed_at=None,
        review_notes=None,
    )
    db = SimpleNamespace(flush=AsyncMock())
    updated = await reject_review(db, document, reviewer_id=2, review_notes="Needs changes")
    assert updated.status == DocumentStatus.DRAFT
    assert updated.review_notes == "Needs changes"
