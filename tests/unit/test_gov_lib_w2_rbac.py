"""Governance Library Wave W2 — facet bundles + restricted RBAC tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.domain.exceptions import NotFoundError
from src.domain.services.document_library_filing_service import assert_library_read_access
from src.domain.services.document_library_rbac import (
    FACET_ADMIN,
    FACET_MANAGER,
    FACET_STAFF,
    facet_permission_bundles,
    merge_facet_into_permissions,
    parse_permissions,
    restricted_permission_for_taxonomy,
    user_can_read_library_document,
)


def test_facet_bundles_cover_document_permissions():
    bundles = facet_permission_bundles()
    assert bundles[FACET_STAFF] == ["document:read"]
    assert "document:update" in bundles[FACET_MANAGER]
    assert "admin:manage" in bundles[FACET_ADMIN]
    assert "document:restricted:oh" in bundles[FACET_ADMIN]
    assert "document:restricted:driver" in bundles[FACET_ADMIN]
    assert "document:restricted:breach" in bundles[FACET_ADMIN]


def test_restricted_taxonomy_permission_map():
    assert restricted_permission_for_taxonomy("02.08") == "document:restricted:oh"
    assert restricted_permission_for_taxonomy("06.03") == "document:restricted:driver"
    assert restricted_permission_for_taxonomy("11.03") == "document:restricted:breach"
    assert restricted_permission_for_taxonomy("04.04") is None


def test_merge_facet_into_permissions_is_union():
    merged = merge_facet_into_permissions('["document:read"]', FACET_MANAGER)
    perms = set(parse_permissions(merged))
    assert perms == {"document:read", "document:create", "document:update"}


def _user(*perms: str):
    allowed = set(perms)
    return SimpleNamespace(
        is_superuser=False,
        has_permission=lambda perm: perm in allowed,
    )


def test_restricted_oh_requires_oh_permission():
    document = SimpleNamespace(access_level="restricted", category_id=1)
    staff = _user("document:read")
    assert user_can_read_library_document(document, staff, taxonomy_id="02.08") is False

    oh = _user("document:restricted:oh")
    assert user_can_read_library_document(document, oh, taxonomy_id="02.08") is True
    assert user_can_read_library_document(document, oh, taxonomy_id="06.03") is False


def test_restricted_isolation_across_facets():
    document = SimpleNamespace(access_level="restricted")
    driver = _user("document:restricted:driver")
    breach = _user("document:restricted:breach")
    assert user_can_read_library_document(document, driver, taxonomy_id="06.03") is True
    assert user_can_read_library_document(document, driver, taxonomy_id="11.03") is False
    assert user_can_read_library_document(document, breach, taxonomy_id="11.03") is True


def test_admin_manage_still_bypasses_restricted():
    document = SimpleNamespace(access_level="restricted")
    admin = _user("admin:manage")
    assert user_can_read_library_document(document, admin, taxonomy_id="02.08") is True


def test_restricted_without_taxonomy_fails_closed():
    document = SimpleNamespace(access_level="restricted")
    manager = _user("document:update")
    assert user_can_read_library_document(document, manager, taxonomy_id=None) is False
    with pytest.raises(NotFoundError):
        assert_library_read_access(document, manager, taxonomy_id=None)


def test_assert_library_read_access_404_for_denied_restricted():
    document = SimpleNamespace(access_level="restricted")
    staff = _user("document:read")
    with pytest.raises(NotFoundError):
        assert_library_read_access(document, staff, taxonomy_id="02.08")

    oh = _user("document:restricted:oh")
    assert_library_read_access(document, oh, taxonomy_id="02.08")
