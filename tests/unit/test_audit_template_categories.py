"""PX-265 — audit template category counts include uncategorised templates."""

import inspect

from src.api.routes import audit_templates as at_routes


def test_list_categories_groups_null_category_as_uncategorised():
    source = inspect.getsource(at_routes.list_categories)
    assert "Uncategorised" in source
    assert "coalesce" in source.lower()
    assert "category.isnot(None)" not in source
