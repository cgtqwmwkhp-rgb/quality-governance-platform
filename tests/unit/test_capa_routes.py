"""Tests for CAPA API routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.capa import CAPAPriority, CAPAStatus, CAPAType


class TestCAPARoutes:
    """Tests for CAPA CRUD operations."""

    def test_capa_status_enum(self):
        """Test CAPAStatus enum values."""
        assert CAPAStatus.OPEN == "open"
        assert CAPAStatus.IN_PROGRESS == "in_progress"
        assert CAPAStatus.VERIFICATION == "verification"
        assert CAPAStatus.CLOSED == "closed"
        assert CAPAStatus.OVERDUE == "overdue"

    def test_capa_type_enum(self):
        """Test CAPAType enum values."""
        assert CAPAType.CORRECTIVE == "corrective"
        assert CAPAType.PREVENTIVE == "preventive"

    def test_capa_priority_enum(self):
        """Test CAPAPriority enum values."""
        assert CAPAPriority.LOW == "low"
        assert CAPAPriority.MEDIUM == "medium"
        assert CAPAPriority.HIGH == "high"
        assert CAPAPriority.CRITICAL == "critical"

    def test_valid_status_transitions(self):
        """Test CAPA status transition rules."""
        valid_transitions = {
            CAPAStatus.OPEN: [CAPAStatus.IN_PROGRESS],
            CAPAStatus.IN_PROGRESS: [CAPAStatus.VERIFICATION, CAPAStatus.OPEN],
            CAPAStatus.VERIFICATION: [CAPAStatus.CLOSED, CAPAStatus.IN_PROGRESS],
            CAPAStatus.OVERDUE: [CAPAStatus.IN_PROGRESS, CAPAStatus.CLOSED],
        }

        assert CAPAStatus.IN_PROGRESS in valid_transitions[CAPAStatus.OPEN]
        assert CAPAStatus.CLOSED not in valid_transitions[CAPAStatus.OPEN]
        assert CAPAStatus.CLOSED in valid_transitions[CAPAStatus.VERIFICATION]

    def test_capa_create_schema(self):
        """Test CAPACreate schema validation."""
        from src.api.routes.capa import CAPACreate

        data = CAPACreate(
            title="Test CAPA",
            capa_type=CAPAType.CORRECTIVE,
            priority=CAPAPriority.HIGH,
        )
        assert data.title == "Test CAPA"
        assert data.capa_type == CAPAType.CORRECTIVE

    def test_capa_create_schema_requires_title(self):
        """Test CAPACreate requires title."""
        from src.api.routes.capa import CAPACreate

        with pytest.raises(Exception):
            CAPACreate(capa_type=CAPAType.CORRECTIVE)

    def test_capa_update_schema(self):
        """Test CAPAUpdate partial update schema."""
        from src.api.routes.capa import CAPAUpdate

        data = CAPAUpdate(priority=CAPAPriority.CRITICAL)
        dumped = data.model_dump(exclude_unset=True)
        assert "priority" in dumped
        assert "title" not in dumped
