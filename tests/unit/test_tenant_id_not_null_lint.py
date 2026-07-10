"""Unit tests for WCS C-01 Phase 1 tenant_id NOT NULL CI lint."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_tenant_id_not_null import audit


def test_tenant_id_not_null_lint_passes_on_current_orm() -> None:
    critical, _advisory, stats = audit()
    assert critical == []
    assert stats["models"] > 0
    assert stats["nullable_owned_grandfathered"] > 0


def test_tenant_id_policy_files_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    assert (root / "docs/governance/tenant_id_nullable_baseline.json").is_file()
    assert (root / "docs/governance/tenant_id_catalog_exceptions.json").is_file()
    assert (root / "docs/governance/tenant_id_nullability_inventory.md").is_file()


def test_new_owned_nullable_would_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a brand-new owned table with nullable tenant_id."""
    import scripts.validate_tenant_id_not_null as mod

    real_collect = mod._collect_models

    class _FakeCol:
        nullable = True

    class _FakeTable:
        c = {"tenant_id": _FakeCol()}

    class FakeOwnedNullable:
        __name__ = "FakeOwnedNullable"
        __tablename__ = "zzz_c01_phase1_fake_owned"
        __table__ = _FakeTable()

    def _collect_with_fake() -> list[type]:
        return [*real_collect(), FakeOwnedNullable]

    monkeypatch.setattr(mod, "_collect_models", _collect_with_fake)
    critical, _advisory, _stats = mod.audit()
    assert any("zzz_c01_phase1_fake_owned" in msg for msg in critical)
