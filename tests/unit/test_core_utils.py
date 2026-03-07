"""Unit tests for shared core utilities (pagination, update)."""

import pytest
from pydantic import BaseModel

from src.core.pagination import PaginatedResponse, PaginationInput
from src.core.update import apply_updates


class TestPaginationInput:
    def test_defaults(self):
        p = PaginationInput()
        assert p.page == 1
        assert p.page_size == 20
        assert p.offset == 0

    def test_page_two(self):
        p = PaginationInput(page=2, page_size=10)
        assert p.page == 2
        assert p.page_size == 10
        assert p.offset == 10

    def test_negative_page_clamped(self):
        p = PaginationInput(page=-5)
        assert p.page == 1
        assert p.offset == 0

    def test_zero_page_clamped(self):
        p = PaginationInput(page=0)
        assert p.page == 1

    def test_page_size_clamped_to_max(self):
        p = PaginationInput(page_size=9999)
        assert p.page_size == 500

    def test_page_size_clamped_to_min(self):
        p = PaginationInput(page_size=0)
        assert p.page_size == 1


class TestPaginatedResponse:
    def test_construction(self):
        r = PaginatedResponse(items=["a", "b"], total=10, page=1, page_size=2, pages=5)
        assert r.items == ["a", "b"]
        assert r.total == 10
        assert r.pages == 5

    def test_empty(self):
        r = PaginatedResponse(items=[], total=0, page=1, page_size=20, pages=0)
        assert len(r.items) == 0
        assert r.pages == 0


class _FakeEntity:
    def __init__(self):
        self.name = "old"
        self.status = "draft"
        self.updated_at = None


class _FakeSchema(BaseModel):
    name: str | None = None
    status: str | None = None


class TestApplyUpdates:
    def test_partial_update(self):
        entity = _FakeEntity()
        schema = _FakeSchema.model_construct(_fields_set={"name"}, name="new")
        result = apply_updates(entity, schema, set_updated_at=False)
        assert entity.name == "new"
        assert entity.status == "draft"
        assert "name" in result

    def test_sets_updated_at(self):
        entity = _FakeEntity()
        schema = _FakeSchema.model_construct(_fields_set={"name"}, name="new")
        apply_updates(entity, schema, set_updated_at=True)
        assert entity.updated_at is not None

    def test_no_updated_at_when_disabled(self):
        entity = _FakeEntity()
        schema = _FakeSchema.model_construct(_fields_set={"name"}, name="new")
        apply_updates(entity, schema, set_updated_at=False)
        assert entity.updated_at is None

    def test_exclude_fields(self):
        entity = _FakeEntity()
        schema = _FakeSchema.model_construct(_fields_set={"name", "status"}, name="new", status="active")
        result = apply_updates(entity, schema, set_updated_at=False, exclude={"status"})
        assert entity.name == "new"
        assert entity.status == "draft"
        assert "status" not in result
