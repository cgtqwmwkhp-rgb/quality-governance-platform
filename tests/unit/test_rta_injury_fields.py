"""Unit tests for RTA third_party_injured rollup helpers."""

from src.domain.services.rta_injury_fields import (
    derive_third_party_injured,
    seed_third_parties_for_injury,
)


def test_derive_from_parties_any_injured():
    assert derive_third_party_injured({"parties": [{"injured": False}, {"injured": True}]}) is True


def test_derive_from_parties_none_injured():
    assert derive_third_party_injured({"parties": [{"injured": False}]}) is False


def test_derive_unknown_without_parties():
    assert derive_third_party_injured(None) is None
    assert derive_third_party_injured({"parties": []}) is None


def test_explicit_excel_flag_wins():
    assert derive_third_party_injured(None, explicit=True) is True
    assert derive_third_party_injured({"parties": []}, explicit=False) is False


def test_seed_parties_when_excel_yes_and_empty():
    seeded = seed_third_parties_for_injury(None, injured=True)
    assert seeded == {"parties": [{"injured": True}]}
    assert derive_third_party_injured(seeded, explicit=True) is True
