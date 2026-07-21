"""Unit tests for Safety lookup similarity / duplicate guards."""

from src.domain.services.lookup_similarity import (
    SIMILAR_THRESHOLD,
    classify_lookup_name,
    find_exact_match,
    find_similar_matches,
    normalise_lookup_key,
    similarity_score,
)


def test_normalise_collapses_spacing_and_punctuation():
    assert normalise_lookup_key("  D  Shackle ") == "d shackle"
    assert normalise_lookup_key("D-Shackle") == "d shackle"
    assert normalise_lookup_key("RCD Tester ") == "rcd tester"


def test_exact_match_ignores_spacing_case():
    hit = find_exact_match("D  Shackle", [(1, "d shackle"), (2, "Bottle Jack")])
    assert hit == (1, "d shackle")


def test_similar_detects_typo_above_threshold():
    matches = find_similar_matches("D Shackel", [(1, "D Shackle"), (2, "Bottle Jack")])
    assert matches
    assert matches[0].id == 1
    assert matches[0].score >= SIMILAR_THRESHOLD


def test_classify_reuse_similar_new():
    candidates = [(1, "D Shackle"), (2, "Torque Wrench")]
    intent, exact, similar = classify_lookup_name("d-shackle", candidates)
    assert intent == "reuse"
    assert exact is not None
    assert similar == []

    intent, exact, similar = classify_lookup_name("D Shackel", candidates)
    assert intent == "similar"
    assert exact is None
    assert similar[0].name == "D Shackle"

    intent, exact, similar = classify_lookup_name("Gas Detector", candidates)
    assert intent == "new"
    assert exact is None
    assert similar == []


def test_unrelated_names_score_low():
    assert similarity_score("Axle Stand", "Microwave") < SIMILAR_THRESHOLD
