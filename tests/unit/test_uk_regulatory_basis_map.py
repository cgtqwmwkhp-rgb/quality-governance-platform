"""Unit tests for the curated UK regulatory basis map."""

from src.domain.data.uk_regulatory_basis_map import UK_REGULATORY_BASIS_MAP, assert_map_integrity, match_uk_regulations


def test_map_integrity() -> None:
    assert_map_integrity()
    assert len(UK_REGULATORY_BASIS_MAP) >= 10


def test_fire_risk_assessment_yields_fso() -> None:
    hits = match_uk_regulations("Fire Risk Assessment", taxonomy_id="03.01", statutory=True)
    assert hits
    assert hits[0][0].code == "FSO2005"
    assert hits[0][1] >= 0.9


def test_fire_drill_yields_fso() -> None:
    hits = match_uk_regulations("Annual fire drill and evacuation practice", taxonomy_id="03.04")
    assert hits
    assert hits[0][0].code == "FSO2005"
    assert hits[0][1] >= 0.9


def test_thorough_examination_yields_loler() -> None:
    hits = match_uk_regulations("Thorough examination of lifting equipment")
    assert hits
    assert hits[0][0].code == "LOLER1998"


def test_eicr_yields_eawr() -> None:
    hits = match_uk_regulations("Fixed wire inspection (EICR)", taxonomy_id="04.02")
    assert hits
    assert hits[0][0].code == "EAWR1989"


def test_legionella_yields_l8() -> None:
    hits = match_uk_regulations("Legionella risk assessment for cooling towers")
    assert hits
    assert hits[0][0].code == "L8"


def test_unrelated_title_stays_below_threshold() -> None:
    hits = match_uk_regulations("Team meeting notes", min_score=0.5)
    assert all(score < 0.5 or entry.code for entry, score in hits)  # may be empty
    assert not any(score >= 0.5 for _, score in hits)
