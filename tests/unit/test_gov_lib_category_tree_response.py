"""Hotfix: category tree must not lazy-load ORM children during response build."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.api.routes.document_categories import (
    DocumentCategoryResponse,
    DocumentCategoryTreeNode,
    get_document_category_tree,
)


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _Scalars(self._rows)


class _OrmCategory:
    """Minimal ORM stand-in with a hostile children relationship."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def children(self):
        raise RuntimeError("lazy children load attempted")


@pytest.mark.asyncio
async def test_category_tree_builds_without_orm_children_access():
    section = _OrmCategory(
        id=1,
        taxonomy_id="01",
        parent_id=None,
        level=1,
        sort_order=1,
        name="Health & Safety",
        slug="health-safety",
        ref_prefix="PEL-HSE",
        description=None,
        default_access="all_staff",
        suggested_owner_role=None,
        review_cycle=None,
        retention_rule=None,
        active=True,
    )
    child = _OrmCategory(
        id=2,
        taxonomy_id="01.01",
        parent_id=1,
        level=2,
        sort_order=1,
        name="Policies",
        slug="policies",
        ref_prefix="PEL-HSE-01",
        description=None,
        default_access="all_staff",
        suggested_owner_role=None,
        review_cycle=None,
        retention_rule=None,
        active=True,
    )

    with pytest.raises(Exception):
        DocumentCategoryTreeNode.model_validate(section, from_attributes=True)

    flat = DocumentCategoryResponse.model_validate(section, from_attributes=True)
    node = DocumentCategoryTreeNode(**flat.model_dump(), children=[])
    assert node.taxonomy_id == "01"
    assert node.children == []

    async def execute(_statement):
        return _Result([section, child])

    db = SimpleNamespace(execute=execute)
    user = SimpleNamespace(id=1, tenant_id=1)

    tree = await get_document_category_tree(db=db, current_user=user, include_inactive=False)
    assert tree.total_categories == 2
    assert tree.total_active == 2
    assert len(tree.sections) == 1
    assert tree.sections[0].taxonomy_id == "01"
    assert len(tree.sections[0].children) == 1
    assert tree.sections[0].children[0].taxonomy_id == "01.01"
