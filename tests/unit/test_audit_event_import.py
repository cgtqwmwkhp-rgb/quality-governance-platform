"""
Tests for AuditEvent import contract and basic functionality.

These tests prevent regression of the ImportError that caused startup crashes.
See: ImportError: cannot import name 'AuditEvent' from 'src.domain.models.audit_log'
"""

import pytest
from datetime import datetime


class TestAuditEventImportContract:
    """Verify AuditEvent can be imported from expected locations."""

    def test_import_audit_event_from_audit_log(self):
        """AuditEvent must be importable from src.domain.models.audit_log."""
        from src.domain.models.audit_log import AuditEvent

        assert AuditEvent is not None
        assert callable(AuditEvent)

    def test_import_audit_service(self):
        """audit_service module must be importable without errors."""
        from src.domain.services import audit_service

        assert audit_service is not None
        assert hasattr(audit_service, "record_audit_event")
        assert callable(audit_service.record_audit_event)

    def test_import_record_audit_event_function(self):
        """record_audit_event function must be importable."""
        from src.domain.services.audit_service import record_audit_event

        assert record_audit_event is not None
        assert callable(record_audit_event)


class TestAuditEventInstantiation:
    """Verify AuditEvent can be instantiated with expected fields."""

    def test_create_audit_event_minimal(self):
        """AuditEvent can be created with minimal required fields."""
        from src.domain.models.audit_log import AuditEvent

        event = AuditEvent(
            event_type="test.created",
            entity_type="test",
            entity_id="123",
            action="create",
        )

        assert event.event_type == "test.created"
        assert event.entity_type == "test"
        assert event.entity_id == "123"
        assert event.action == "create"
        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)

    def test_create_audit_event_full(self):
        """AuditEvent can be created with all fields."""
        from src.domain.models.audit_log import AuditEvent

        event = AuditEvent(
            event_type="policy.updated",
            entity_type="policy",
            entity_id="456",
            action="update",
            description="Updated policy title",
            payload={"old_title": "Old", "new_title": "New"},
            actor_user_id=1,
            request_id="req-123-456",
            resource_type="policy",
            resource_id="456",
            user_id=1,
        )

        assert event.event_type == "policy.updated"
        assert event.description == "Updated policy title"
        assert event.payload == {"old_title": "Old", "new_title": "New"}
        assert event.actor_user_id == 1
        assert event.request_id == "req-123-456"
        assert event.resource_type == "policy"
        assert event.user_id == 1

    def test_audit_event_repr(self):
        """AuditEvent has a useful string representation."""
        from src.domain.models.audit_log import AuditEvent

        event = AuditEvent(
            event_type="incident.created",
            entity_type="incident",
            entity_id="789",
            action="create",
        )

        repr_str = repr(event)
        assert "AuditEvent" in repr_str
        assert "incident.created" in repr_str
        assert "incident:789" in repr_str


class TestAuditLogEntryStillExists:
    """Verify AuditLogEntry (blockchain-style) still exists and works."""

    def test_import_audit_log_entry(self):
        """AuditLogEntry must still be importable."""
        from src.domain.models.audit_log import AuditLogEntry

        assert AuditLogEntry is not None
        assert hasattr(AuditLogEntry, "__tablename__")
        assert AuditLogEntry.__tablename__ == "audit_log_entries"

    def test_audit_log_entry_has_required_fields(self):
        """AuditLogEntry has the blockchain-style required fields."""
        from src.domain.models.audit_log import AuditLogEntry

        # Check key columns exist
        columns = AuditLogEntry.__table__.columns.keys()

        assert "id" in columns
        assert "tenant_id" in columns
        assert "sequence" in columns
        assert "entry_hash" in columns
        assert "previous_hash" in columns
        assert "entity_type" in columns
        assert "entity_id" in columns
        assert "action" in columns
        assert "user_id" in columns
        assert "timestamp" in columns
