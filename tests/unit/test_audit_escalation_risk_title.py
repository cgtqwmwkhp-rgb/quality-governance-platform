"""Unit tests for audit escalation risk title resolution and backfill."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.audit_escalation_risk_title import (
    backfill_descriptive_escalation_titles,
    build_audit_escalation_risk_title,
    is_generic_audit_escalation_title,
    upgrade_generic_escalation_title,
)


def _finding(**overrides):
    defaults = {
        "title": "Inadequate fire door maintenance records",
        "description": "Site inspection found missing quarterly checks on fire doors across Block B.",
        "reference_number": "FND-2026-0168",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Audit escalation: AUD-2026-0053 / FND-2026-0168", True),
        ("Imported audit escalation: Missing PPE records", True),
        ("Inadequate fire door maintenance records", False),
        ("Address imported audit issue: Competence gap", False),
        (None, False),
    ],
)
def test_is_generic_audit_escalation_title(title: str | None, expected: bool) -> None:
    assert is_generic_audit_escalation_title(title) is expected


def test_build_title_prefers_non_generic_suggested_title() -> None:
    title = build_audit_escalation_risk_title(
        finding=_finding(),
        run_reference_number="AUD-2026-0053",
        suggested_title="Custom risk from import review",
    )
    assert title == "Custom risk from import review"


def test_build_title_ignores_generic_suggested_title_and_uses_finding_title() -> None:
    title = build_audit_escalation_risk_title(
        finding=_finding(title="Competence gap on LOLER inspections"),
        run_reference_number="AUD-2026-0053",
        suggested_title="Imported audit escalation: Competence gap on LOLER inspections",
    )
    assert title.startswith("Competence gap on LOLER inspections")
    assert "FND-2026-0168" in title


def test_build_title_falls_back_to_description_preview() -> None:
    long_description = " ".join(["Detailed audit narrative"] * 20)
    title = build_audit_escalation_risk_title(
        finding=_finding(title="FND-2026-0168", description=long_description),
        run_reference_number="AUD-2026-0053",
    )
    assert title.startswith("Detailed audit narrative")
    assert len(title) <= 255


def test_build_title_uses_ref_fallback_when_no_descriptive_source() -> None:
    title = build_audit_escalation_risk_title(
        finding=_finding(title="", description=""),
        run_reference_number="AUD-2026-0053",
    )
    assert title == "Audit escalation: AUD-2026-0053 / FND-2026-0168"


def test_upgrade_generic_escalation_title_returns_none_for_descriptive_existing() -> None:
    upgraded = upgrade_generic_escalation_title(
        "Competence gap on LOLER inspections",
        finding=_finding(),
        run_reference_number="AUD-2026-0053",
    )
    assert upgraded is None


def test_upgrade_generic_escalation_title_rewrites_legacy_label() -> None:
    upgraded = upgrade_generic_escalation_title(
        "Audit escalation: AUD-2026-0053 / FND-2026-0168",
        finding=_finding(),
        run_reference_number="AUD-2026-0053",
    )
    assert upgraded is not None
    assert upgraded.startswith("Inadequate fire door maintenance records")


@pytest.mark.asyncio
async def test_backfill_dry_run_reports_would_update() -> None:
    risk = SimpleNamespace(
        id=7,
        reference="RSK-2026-0001",
        title="Audit escalation: AUD-2026-0053 / FND-2026-0168",
        linked_audits=["AUD-2026-0053", "FND-2026-0168"],
    )
    finding = SimpleNamespace(
        id=11,
        title="Inadequate fire door maintenance records",
        description="Missing quarterly checks.",
        reference_number="FND-2026-0168",
        tenant_id=1,
    )

    class _Scalars:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

        def first(self):
            return self._items[0] if self._items else None

    class _Result:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return _Scalars(self._items)

        def scalar_one_or_none(self):
            return self._items[0] if self._items else None

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _Result([risk]),
            _Result([finding]),
        ]
    )
    db.commit = AsyncMock()

    result = await backfill_descriptive_escalation_titles(db, tenant_id=1, commit=False)

    assert result["dry_run"] is True
    assert result["would_update_count"] == 1
    assert result["updated_count"] == 0
    assert result["changes"][0]["old_title"].startswith("Audit escalation:")
    assert result["changes"][0]["new_title"].startswith("Inadequate fire door maintenance records")
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_backfill_commit_persists_title_upgrades() -> None:
    risk = SimpleNamespace(
        id=7,
        reference="RSK-2026-0001",
        title="Audit escalation: AUD-2026-0053 / FND-2026-0168",
        linked_audits=["AUD-2026-0053", "FND-2026-0168"],
    )
    finding = SimpleNamespace(
        id=11,
        title="Inadequate fire door maintenance records",
        description="Missing quarterly checks.",
        reference_number="FND-2026-0168",
        tenant_id=1,
    )

    class _Scalars:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

        def first(self):
            return self._items[0] if self._items else None

    class _Result:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return _Scalars(self._items)

        def scalar_one_or_none(self):
            return self._items[0] if self._items else None

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _Result([risk]),
            _Result([finding]),
        ]
    )
    db.commit = AsyncMock()

    result = await backfill_descriptive_escalation_titles(db, tenant_id=1, commit=True)

    assert result["dry_run"] is False
    assert result["updated_count"] == 1
    assert risk.title.startswith("Inadequate fire door maintenance records")
    db.commit.assert_awaited_once()
