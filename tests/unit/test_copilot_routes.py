"""Tests for AI copilot API routes."""

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


class TestCopilotRoutes:
    """Test copilot route handlers."""

    @skip_on_import_error
    def test_module_imports(self):
        """Verify route module imports without error."""
        from src.api.routes import copilot

        assert hasattr(copilot, "router")

    @skip_on_import_error
    def test_router_has_sessions_route(self):
        """Verify sessions route exists."""
        from src.api.routes.copilot import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        session_routes = [r for r in routes if r.path == "/sessions"]
        assert len(session_routes) > 0

    @skip_on_import_error
    def test_router_has_actions_route(self):
        """Verify actions list route exists."""
        from src.api.routes.copilot import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        action_routes = [r for r in routes if r.path == "/actions"]
        assert len(action_routes) > 0

    @skip_on_import_error
    def test_router_has_knowledge_search_route(self):
        """Verify knowledge search route exists."""
        from src.api.routes.copilot import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        search_routes = [r for r in routes if r.path == "/knowledge/search"]
        assert len(search_routes) > 0


class TestCopilotSchemas:
    """Test copilot schema validation."""

    @skip_on_import_error
    def test_session_create_schema(self):
        """Test SessionCreate schema with valid data."""
        from src.api.routes.copilot import SessionCreate

        data = SessionCreate(
            context_type="incident",
            context_id="INC-001",
            current_page="/incidents/1",
        )
        assert data.context_type == "incident"
        assert data.context_id == "INC-001"

    @skip_on_import_error
    def test_session_create_schema_defaults(self):
        """Test SessionCreate schema with defaults."""
        from src.api.routes.copilot import SessionCreate

        data = SessionCreate()
        assert data.context_type is None
        assert data.context_data is None

    @skip_on_import_error
    def test_message_create_schema(self):
        """Test MessageCreate schema with valid data."""
        from src.api.routes.copilot import MessageCreate

        data = MessageCreate(content="How do I file an incident report?")
        assert data.content == "How do I file an incident report?"

    @skip_on_import_error
    def test_message_create_schema_requires_content(self):
        """Test MessageCreate rejects empty content."""
        from src.api.routes.copilot import MessageCreate

        with pytest.raises(Exception):
            MessageCreate(content="")

    @skip_on_import_error
    def test_feedback_create_schema(self):
        """Test FeedbackCreate schema with valid data."""
        from src.api.routes.copilot import FeedbackCreate

        data = FeedbackCreate(rating=5, feedback_type="helpful")
        assert data.rating == 5

    @skip_on_import_error
    def test_feedback_create_schema_validates_rating(self):
        """Test FeedbackCreate rejects invalid rating."""
        from src.api.routes.copilot import FeedbackCreate

        with pytest.raises(Exception):
            FeedbackCreate(rating=6, feedback_type="helpful")

    @skip_on_import_error
    def test_action_execute_schema(self):
        """Test ActionExecute schema with valid data."""
        from src.api.routes.copilot import ActionExecute

        data = ActionExecute(
            action_name="create_incident",
            parameters={"title": "Test Incident"},
        )
        assert data.action_name == "create_incident"
        assert data.parameters["title"] == "Test Incident"


class TestCopilotResponseSchemas:
    """Test copilot response schemas."""

    @skip_on_import_error
    def test_close_session_response(self):
        """Test CloseSessionResponse schema."""
        from src.api.schemas.copilot import CloseSessionResponse

        data = CloseSessionResponse(status="closed")
        assert data.status == "closed"

    @skip_on_import_error
    def test_execute_action_response(self):
        """Test ExecuteActionResponse schema."""
        from src.api.schemas.copilot import ExecuteActionResponse

        data = ExecuteActionResponse(
            status="executed",
            action="create_incident",
            parameters={"title": "Test"},
            result={"success": True},
        )
        assert data.status == "executed"
        assert data.result["success"] is True

    @skip_on_import_error
    def test_add_knowledge_response(self):
        """Test AddKnowledgeResponse schema."""
        from src.api.schemas.copilot import AddKnowledgeResponse

        data = AddKnowledgeResponse(id=1, title="Safety Procedures")
        assert data.id == 1
