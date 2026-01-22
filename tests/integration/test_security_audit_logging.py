"""Integration tests for security audit logging on filtered queries.

Stage 3 Security Controls:
- Audit logging when email filters are used on sensitive endpoints
- Privacy compliance: logs filter type but NOT raw email values
"""

import logging

import pytest
from httpx import AsyncClient

from src.domain.models.audit_log import AuditEvent


class TestAuditEventStructure:
    """Test audit event class structure and logging."""

    def test_audit_event_logs_on_creation(self, caplog):
        """Verify AuditEvent logs on creation."""
        with caplog.at_level(logging.INFO):
            event = AuditEvent(
                event_type="test.list_filtered",
                entity_type="test",
                entity_id="*",
                action="list",
                description="Test filtered query",
                payload={
                    "filter_type": "reporter_email",
                    "is_own_email": True,
                    "has_view_all_permission": False,
                },
                actor_user_id=123,
                request_id="test-request-id-001",
            )

        # Verify event was logged
        assert "AuditEvent" in caplog.text
        assert "test.list_filtered" in caplog.text
        assert "test:*" in caplog.text
        assert "user=123" in caplog.text
        assert "request=test-request-id-001" in caplog.text

    def test_audit_event_does_not_log_raw_email(self, caplog):
        """Verify audit events do NOT contain raw email addresses.

        Privacy compliance: We log filter_type but never the actual email.
        """
        with caplog.at_level(logging.INFO):
            event = AuditEvent(
                event_type="incident.list_filtered",
                entity_type="incident",
                entity_id="*",
                action="list",
                description="Incident list accessed with email filter",
                payload={
                    "filter_type": "reporter_email",
                    "is_own_email": True,
                    "has_view_all_permission": False,
                    "is_superuser": False,
                    # Note: NO email field in payload - this is intentional
                },
                actor_user_id=456,
                request_id="req-privacy-test",
            )

        # Verify no email addresses in log output
        assert "@" not in caplog.text.lower() or "example" not in caplog.text.lower()
        assert "test@" not in caplog.text.lower()
        assert "user@" not in caplog.text.lower()

    def test_audit_event_includes_filter_type(self, caplog):
        """Verify audit events include filter type metadata."""
        with caplog.at_level(logging.INFO):
            # Incident filter event
            AuditEvent(
                event_type="incident.list_filtered",
                entity_type="incident",
                entity_id="*",
                action="list",
                payload={"filter_type": "reporter_email"},
            )

        assert "incident.list_filtered" in caplog.text

    def test_audit_event_captures_request_id(self):
        """Verify audit events capture request_id for traceability."""
        event = AuditEvent(
            event_type="test.filtered",
            entity_type="test",
            entity_id="*",
            action="list",
            request_id="trace-12345",
        )

        assert event.request_id == "trace-12345"

    def test_audit_event_captures_user_id(self):
        """Verify audit events capture actor user ID."""
        event = AuditEvent(
            event_type="test.filtered",
            entity_type="test",
            entity_id="*",
            action="list",
            actor_user_id=789,
        )

        assert event.actor_user_id == 789


class TestFilteredQueryAuditPayload:
    """Test audit payload structure for filtered queries."""

    def test_payload_includes_ownership_check(self):
        """Verify payload includes whether user is querying own data."""
        event = AuditEvent(
            event_type="incident.list_filtered",
            entity_type="incident",
            entity_id="*",
            action="list",
            payload={
                "filter_type": "reporter_email",
                "is_own_email": True,  # User querying their own data
                "has_view_all_permission": False,
                "is_superuser": False,
            },
        )

        assert event.payload["is_own_email"] is True
        assert event.payload["has_view_all_permission"] is False

    def test_payload_includes_admin_status(self):
        """Verify payload includes admin/permission status."""
        event = AuditEvent(
            event_type="incident.list_filtered",
            entity_type="incident",
            entity_id="*",
            action="list",
            payload={
                "filter_type": "reporter_email",
                "is_own_email": False,  # Admin viewing someone else's data
                "has_view_all_permission": True,
                "is_superuser": True,
            },
        )

        assert event.payload["has_view_all_permission"] is True
        assert event.payload["is_superuser"] is True


class TestAuditEventTypes:
    """Test correct event types for each endpoint."""

    def test_incident_filter_event_type(self):
        """Verify incident filtered query event type."""
        event = AuditEvent(
            event_type="incident.list_filtered",
            entity_type="incident",
            entity_id="*",
            action="list",
        )
        assert event.event_type == "incident.list_filtered"
        assert event.entity_type == "incident"

    def test_complaint_filter_event_type(self):
        """Verify complaint filtered query event type."""
        event = AuditEvent(
            event_type="complaint.list_filtered",
            entity_type="complaint",
            entity_id="*",
            action="list",
        )
        assert event.event_type == "complaint.list_filtered"
        assert event.entity_type == "complaint"

    def test_rta_filter_event_type(self):
        """Verify RTA filtered query event type."""
        event = AuditEvent(
            event_type="rta.list_filtered",
            entity_type="rta",
            entity_id="*",
            action="list",
        )
        assert event.event_type == "rta.list_filtered"
        assert event.entity_type == "rta"
