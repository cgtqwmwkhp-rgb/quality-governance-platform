"""B-10: AccessControlCreate must reject unknown body fields (extra=forbid)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.api.routes.iso27001 import AccessControlCreate


def test_access_control_create_accepts_known_fields() -> None:
    granted = datetime(2026, 1, 15, tzinfo=timezone.utc)
    m = AccessControlCreate(
        user_id=7,
        user_name="Ada Lovelace",
        user_email="ada@example.com",
        user_department="Engineering",
        system_name="QGP",
        access_level="read",
        granted_date=granted,
        granted_by="admin",
        expiry_date=None,
    )
    assert m.user_id == 7
    assert m.system_name == "QGP"
    assert m.access_level == "read"


def test_access_control_create_optionals_default_none() -> None:
    granted = datetime(2026, 1, 15, tzinfo=timezone.utc)
    m = AccessControlCreate(
        user_id=1,
        user_name="User",
        system_name="QGP",
        access_level="read",
        granted_date=granted,
    )
    assert m.user_email is None
    assert m.user_department is None
    assert m.granted_by is None
    assert m.expiry_date is None


def test_access_control_create_rejects_unknown_fields() -> None:
    granted = datetime(2026, 1, 15, tzinfo=timezone.utc)
    with pytest.raises(ValidationError) as exc_info:
        AccessControlCreate(
            user_id=1,
            user_name="User",
            system_name="QGP",
            access_level="read",
            granted_date=granted,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
