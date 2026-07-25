from datetime import datetime, timedelta, timezone

import pytest

from src.domain.services.assurance_cert_shelf_service import (
    DEFAULT_DUE_SOON_DAYS,
    AssuranceCertShelfService,
    _build_item,
    compute_readiness_status,
)

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("expiry_offset_days", "expected"),
    [
        (-1, "expired"),
        (0, "due_soon"),
        (10, "due_soon"),
        (30, "due_soon"),
        (31, "valid"),
    ],
)
def test_compute_readiness_status(expiry_offset_days, expected):
    expiry = NOW + timedelta(days=expiry_offset_days)
    assert compute_readiness_status(expiry, due_soon_days=DEFAULT_DUE_SOON_DAYS, now=NOW) == expected


def test_compute_readiness_status_unknown_when_missing_expiry():
    assert compute_readiness_status(None, due_soon_days=DEFAULT_DUE_SOON_DAYS, now=NOW) == "unknown"


def test_build_item_summary_counts():
    items = [
        _build_item(
            shelf_key="a",
            name="Valid cert",
            scheme="register",
            source="compliance_register",
            expiry_date=NOW + timedelta(days=120),
            due_soon_days=30,
            now=NOW,
        ),
        _build_item(
            shelf_key="b",
            name="Due soon cert",
            scheme="planet_mark",
            source="planet_mark",
            expiry_date=NOW + timedelta(days=5),
            due_soon_days=30,
            now=NOW,
        ),
        _build_item(
            shelf_key="c",
            name="Expired cert",
            scheme="uvdb_achilles",
            source="uvdb_achilles",
            expiry_date=NOW - timedelta(days=1),
            due_soon_days=30,
            now=NOW,
        ),
    ]
    summary = AssuranceCertShelfService._build_summary(items)
    assert summary["valid"] == 1
    assert summary["due_soon"] == 1
    assert summary["expired"] == 1
    assert summary["by_scheme"]["register"] == 1
    assert summary["by_scheme"]["planet_mark"] == 1


def test_build_item_grades_against_injected_now_not_wall_clock():
    """Readiness must depend only on the supplied reference instant.

    Without this, a fixture expiry silently changes meaning as real time passes and the
    suite starts failing on a date rather than on a code change.
    """
    expiry = NOW + timedelta(days=5)
    common = {
        "shelf_key": "a",
        "name": "Cert",
        "scheme": "register",
        "source": "compliance_register",
        "due_soon_days": 30,
    }

    assert _build_item(expiry_date=expiry, now=NOW, **common)["readiness_status"] == "due_soon"
    assert _build_item(expiry_date=expiry, now=NOW - timedelta(days=90), **common)["readiness_status"] == "valid"
    assert _build_item(expiry_date=expiry, now=NOW + timedelta(days=400), **common)["readiness_status"] == "expired"
