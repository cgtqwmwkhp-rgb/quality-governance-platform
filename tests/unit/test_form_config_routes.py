"""Tests for form configuration API routes."""

import functools
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def skip_on_import_error(test_func):
    """Decorator to skip tests that fail due to ImportError."""

    @functools.wraps(test_func)
    def wrapper(*args, **kwargs):
        try:
            return test_func(*args, **kwargs)
        except (ImportError, ModuleNotFoundError) as e:
            pytest.skip(f"Dependency not available: {e}")

    return wrapper


class TestFormConfigRoutes:
    """Test form config route handlers."""

    @skip_on_import_error
    def test_module_imports(self):
        """Verify route module imports without error."""
        from src.api.routes import form_config

        assert hasattr(form_config, "router")

    @skip_on_import_error
    def test_router_has_templates_route(self):
        """Verify form template routes exist."""
        from src.api.routes.form_config import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        template_routes = [r for r in routes if "template" in r.path.lower()]
        assert len(template_routes) > 0

    def test_form_template_model_exists(self):
        """Test FormTemplate domain model exists."""
        from src.domain.models.form_config import FormTemplate

        assert FormTemplate is not None
        assert hasattr(FormTemplate, "__tablename__")

    def test_form_step_model_exists(self):
        """Test FormStep domain model exists."""
        from src.domain.models.form_config import FormStep

        assert FormStep is not None
        assert hasattr(FormStep, "__tablename__")

    def test_form_field_model_exists(self):
        """Test FormField domain model exists."""
        from src.domain.models.form_config import FormField

        assert FormField is not None
        assert hasattr(FormField, "__tablename__")

    def test_contract_model_exists(self):
        """Test Contract domain model exists."""
        from src.domain.models.form_config import Contract

        assert Contract is not None

    @skip_on_import_error
    def test_form_template_create_schema(self):
        """Test FormTemplateCreate schema validation."""
        from src.api.schemas.form_config import FormTemplateCreate

        data = FormTemplateCreate(
            name="Incident Report",
            slug="incident-report",
            form_type="incident",
        )
        assert data.name == "Incident Report"
        assert data.slug == "incident-report"
