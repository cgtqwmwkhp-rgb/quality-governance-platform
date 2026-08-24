"""Unit tests for Northern Star W4 / NS-RULE-A identity hard blocks."""

from __future__ import annotations

import pytest

from src.domain.exceptions import ValidationError
from src.domain.services.library_rules import (
    RULE_A_IDS,
    assert_access_level_required,
    assert_filename_grammar_if_pel_prefixed,
    assert_pel_identity,
    filename_grammar_pattern,
    reference_pattern,
)


def test_rule_a_covers_the_identity_block_set():
    assert RULE_A_IDS == {"R01", "R02", "R03", "R04", "R05", "R06", "R26", "R29", "R32"}


def test_reference_pattern_matches_banded_v6_refs():
    assert reference_pattern().fullmatch("PEL-HSEQ-3001")
    assert reference_pattern().fullmatch("PEL-CTR-1001")
    assert reference_pattern().fullmatch("PEL-SVC-4500")
    assert not reference_pattern().fullmatch("PEL-OPS-3001")
    assert not reference_pattern().fullmatch("PEL-HSEQ-0001")


def test_assert_pel_identity_accepts_a_well_formed_ref():
    assert_pel_identity("PEL-IT-3014", function_code="IT", cascade_level=3)


@pytest.mark.parametrize(
    "ref,code,level,rule",
    [
        ("PEL-IT-0014", "IT", 3, "R01"),
        ("PEL-IT-3014", "IT", 2, "R02"),
        ("PEL-IT-3014", "HSEQ", 3, "R03"),
    ],
)
def test_assert_pel_identity_blocks_broken_identity(ref, code, level, rule):
    with pytest.raises(ValidationError, match=rule):
        assert_pel_identity(ref, function_code=code, cascade_level=level)


def test_assert_access_level_required_defaults_path():
    assert assert_access_level_required("all_staff") == "all_staff"
    assert assert_access_level_required("Managers") == "managers"
    with pytest.raises(ValidationError, match="R26"):
        assert_access_level_required(None)
    with pytest.raises(ValidationError, match="R26"):
        assert_access_level_required("secret")


def test_filename_grammar_blocks_malformed_pel_prefixed_names():
    good = "PEL-HSEQ-3001 Control of Substances Hazardous to Health v1.pdf"
    assert filename_grammar_pattern().fullmatch(good)
    assert_filename_grammar_if_pel_prefixed(good)
    # Non-PEL working titles are allowed on the wizard allocate path.
    assert_filename_grammar_if_pel_prefixed("working-title-draft.docx")
    with pytest.raises(ValidationError, match="R32"):
        assert_filename_grammar_if_pel_prefixed("PEL-HSEQ-3001 bad_name_no_version.pdf")
