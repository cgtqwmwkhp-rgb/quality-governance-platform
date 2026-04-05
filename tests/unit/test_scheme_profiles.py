"""Scheme profile canonicalisation for external audit analysis."""

from src.domain.services.scheme_profiles import canonical_scheme_id, get_profile, validate_against_scheme


def test_canonical_scheme_id_iso_family() -> None:
    assert canonical_scheme_id("iso") == "iso"
    assert canonical_scheme_id("ISO_9001") == "iso"
    assert canonical_scheme_id("iso-14001") == "iso"
    assert canonical_scheme_id("achilles_uvdb") == "achilles_uvdb"
    assert canonical_scheme_id("planet_mark") == "planet_mark"


def test_get_profile_resolves_iso_prefixed_ids() -> None:
    profile = get_profile("iso_27001")
    assert profile is not None
    assert profile.scheme_id == "iso"


def test_validate_against_scheme_uses_iso_profile_for_iso_prefix() -> None:
    warnings = validate_against_scheme(
        "iso_45001", overall_score=99.0, max_score=None, score_percentage=None, score_breakdown=None
    )
    assert any("typically do not use numeric scores" in w for w in warnings)
