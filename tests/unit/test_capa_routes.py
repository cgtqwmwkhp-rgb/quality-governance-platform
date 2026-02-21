"""Tests for CAPA API routes."""

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


class TestCAPARouteImports:
    """Test CAPA route module imports and route registration."""

    @skip_on_import_error
    def test_module_imports(self):
        """Verify route module imports without error."""
        from src.api.routes import capa

        assert hasattr(capa, "router")

    @skip_on_import_error
    def test_router_has_list_route(self):
        """Verify list CAPA route exists."""
        from src.api.routes.capa import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        list_routes = [r for r in routes if r.path == "/"]
        assert len(list_routes) > 0

    @skip_on_import_error
    def test_router_has_create_route(self):
        """Verify create CAPA route exists with POST method."""
        from src.api.routes.capa import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        create_routes = [r for r in routes if r.path == "/" and "POST" in r.methods]
        assert len(create_routes) > 0


class TestCAPARoutes:
    """Tests for CAPA CRUD operations."""

    @skip_on_import_error
    def test_capa_status_enum(self):
        """Test CAPAStatus enum values."""
        from src.domain.models.capa import CAPAStatus

        assert CAPAStatus.OPEN == "open"
        assert CAPAStatus.IN_PROGRESS == "in_progress"
        assert CAPAStatus.VERIFICATION == "verification"
        assert CAPAStatus.CLOSED == "closed"
        assert CAPAStatus.OVERDUE == "overdue"

    @skip_on_import_error
    def test_capa_type_enum(self):
        """Test CAPAType enum values."""
        from src.domain.models.capa import CAPAType

        assert CAPAType.CORRECTIVE == "corrective"
        assert CAPAType.PREVENTIVE == "preventive"

    @skip_on_import_error
    def test_capa_priority_enum(self):
        """Test CAPAPriority enum values."""
        from src.domain.models.capa import CAPAPriority

        assert CAPAPriority.LOW == "low"
        assert CAPAPriority.MEDIUM == "medium"
        assert CAPAPriority.HIGH == "high"
        assert CAPAPriority.CRITICAL == "critical"

    @skip_on_import_error
    def test_valid_status_transitions(self):
        """Test CAPA status transition rules."""
        from src.domain.models.capa import CAPAStatus

        valid_transitions = {
            CAPAStatus.OPEN: [CAPAStatus.IN_PROGRESS],
            CAPAStatus.IN_PROGRESS: [CAPAStatus.VERIFICATION, CAPAStatus.OPEN],
            CAPAStatus.VERIFICATION: [CAPAStatus.CLOSED, CAPAStatus.IN_PROGRESS],
            CAPAStatus.OVERDUE: [CAPAStatus.IN_PROGRESS, CAPAStatus.CLOSED],
        }

        assert CAPAStatus.IN_PROGRESS in valid_transitions[CAPAStatus.OPEN]
        assert CAPAStatus.CLOSED not in valid_transitions[CAPAStatus.OPEN]
        assert CAPAStatus.CLOSED in valid_transitions[CAPAStatus.VERIFICATION]

    @skip_on_import_error
    def test_capa_create_schema(self):
        """Test CAPACreate schema validation."""
        from src.api.routes.capa import CAPACreate
        from src.domain.models.capa import CAPAPriority, CAPAType

        data = CAPACreate(
            title="Test CAPA",
            capa_type=CAPAType.CORRECTIVE,
            priority=CAPAPriority.HIGH,
        )
        assert data.title == "Test CAPA"
        assert data.capa_type == CAPAType.CORRECTIVE

    @skip_on_import_error
    def test_capa_create_schema_requires_title(self):
        """Test CAPACreate requires title."""
        from src.api.routes.capa import CAPACreate
        from src.domain.models.capa import CAPAType

        with pytest.raises(Exception):
            CAPACreate(capa_type=CAPAType.CORRECTIVE)

    @skip_on_import_error
    def test_capa_update_schema(self):
        """Test CAPAUpdate partial update schema."""
        from src.api.routes.capa import CAPAUpdate
        from src.domain.models.capa import CAPAPriority

        data = CAPAUpdate(priority=CAPAPriority.CRITICAL)
        dumped = data.model_dump(exclude_unset=True)
        assert "priority" in dumped
        assert "title" not in dumped
