"""Unit tests for PX-177 case soft-delete is_deleted properties."""

from datetime import datetime, timezone
from types import SimpleNamespace

from src.domain.models.complaint import Complaint, ComplaintAction
from src.domain.models.incident import Incident, IncidentAction


def test_incident_is_deleted_property():
    assert Incident.is_deleted.fget(SimpleNamespace(deleted_at=None)) is False
    assert Incident.is_deleted.fget(SimpleNamespace(deleted_at=datetime.now(timezone.utc))) is True


def test_complaint_is_deleted_property():
    assert Complaint.is_deleted.fget(SimpleNamespace(deleted_at=None)) is False
    assert Complaint.is_deleted.fget(SimpleNamespace(deleted_at=datetime.now(timezone.utc))) is True


def test_action_is_deleted_properties():
    now = datetime.now(timezone.utc)
    assert IncidentAction.is_deleted.fget(SimpleNamespace(deleted_at=None)) is False
    assert IncidentAction.is_deleted.fget(SimpleNamespace(deleted_at=now)) is True
    assert ComplaintAction.is_deleted.fget(SimpleNamespace(deleted_at=None)) is False
    assert ComplaintAction.is_deleted.fget(SimpleNamespace(deleted_at=now)) is True
