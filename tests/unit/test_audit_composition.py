"""Unit tests for branching composition helpers (audit_composition.py)."""

from __future__ import annotations

from types import SimpleNamespace

from src.domain.services.audit_composition import (
    compose_template_questions,
    question_is_applicable,
    section_is_applicable,
)


def _section(id_=1, rules=None):
    return SimpleNamespace(id=id_, applicability_rules_json=rules)


def _question(id_, section_id=None, is_active=True):
    return SimpleNamespace(id=id_, section_id=section_id, is_active=is_active)


class TestSectionIsApplicable:
    def test_no_rules_always_applicable(self):
        section = _section(rules=None)
        assert section_is_applicable(section, assessment_mode="full", asset_type_id=1) is True
        assert section_is_applicable(section, assessment_mode=None, asset_type_id=None) is True

    def test_empty_rules_dict_always_applicable(self):
        section = _section(rules={})
        assert section_is_applicable(section, assessment_mode="spot_check") is True

    def test_assessment_mode_restriction_matches(self):
        section = _section(rules={"assessment_modes": ["full", "post_incident"]})
        assert section_is_applicable(section, assessment_mode="full") is True
        assert section_is_applicable(section, assessment_mode="spot_check") is False
        assert section_is_applicable(section, assessment_mode=None) is False

    def test_asset_type_restriction_matches(self):
        section = _section(rules={"asset_type_ids": [1, 2]})
        assert section_is_applicable(section, asset_type_id=1) is True
        assert section_is_applicable(section, asset_type_id=3) is False
        assert section_is_applicable(section, asset_type_id=None) is False

    def test_both_dimensions_must_match(self):
        section = _section(rules={"assessment_modes": ["full"], "asset_type_ids": [1]})
        assert section_is_applicable(section, assessment_mode="full", asset_type_id=1) is True
        assert section_is_applicable(section, assessment_mode="full", asset_type_id=2) is False
        assert section_is_applicable(section, assessment_mode="spot_check", asset_type_id=1) is False

    def test_none_values_in_rule_list_are_unrestricted(self):
        section = _section(rules={"assessment_modes": None, "asset_type_ids": None})
        assert section_is_applicable(section, assessment_mode="anything", asset_type_id=999) is True


class TestQuestionIsApplicable:
    def test_inherits_section_applicability(self):
        section = _section(rules={"assessment_modes": ["full"]})
        question = _question(1, section_id=section.id)
        assert question_is_applicable(question, section=section, assessment_mode="full") is True
        assert question_is_applicable(question, section=section, assessment_mode="spot_check") is False

    def test_no_section_always_applicable(self):
        question = _question(1, section_id=None)
        assert question_is_applicable(question, section=None, assessment_mode="anything") is True

    def test_falls_back_to_question_section_relationship(self):
        section = _section(rules={"assessment_modes": ["full"]})
        question = SimpleNamespace(id=1, section_id=section.id, section=section)
        assert question_is_applicable(question, assessment_mode="full") is True
        assert question_is_applicable(question, assessment_mode="spot_check") is False


class TestComposeTemplateQuestions:
    def test_composes_from_template_like_object(self):
        section_a = _section(1, rules={"assessment_modes": ["full"]})
        section_b = _section(2, rules=None)
        q1 = _question(101, section_id=1)
        q2 = _question(102, section_id=2)
        q3 = _question(103, section_id=None)
        section_a.questions = [q1]
        section_b.questions = [q2]
        template = SimpleNamespace(sections=[section_a, section_b], questions=[q1, q2, q3])

        applicable_full = compose_template_questions(template, assessment_mode="full", asset_type_id=None)
        assert applicable_full == {101, 102, 103}

        applicable_spot = compose_template_questions(template, assessment_mode="spot_check", asset_type_id=None)
        assert applicable_spot == {102, 103}

    def test_excludes_inactive_questions(self):
        section = _section(1, rules=None)
        q1 = _question(101, section_id=1, is_active=True)
        q2 = _question(102, section_id=1, is_active=False)
        section.questions = [q1, q2]
        template = SimpleNamespace(sections=[section], questions=[q1, q2])

        applicable = compose_template_questions(template, assessment_mode="full", asset_type_id=None)
        assert applicable == {101}

    def test_accepts_plain_sections_and_questions_iterables(self):
        section = _section(1, rules={"asset_type_ids": [5]})
        q1 = _question(101, section_id=1)
        q2 = _question(102, section_id=None)

        applicable = compose_template_questions([section], assessment_mode=None, asset_type_id=5, questions=[q1, q2])
        assert applicable == {101, 102}

        not_applicable = compose_template_questions(
            [section], assessment_mode=None, asset_type_id=9, questions=[q1, q2]
        )
        assert not_applicable == {102}

    def test_unresolvable_section_reference_fails_open(self):
        q1 = _question(101, section_id=999)  # section 999 not supplied
        template = SimpleNamespace(sections=[], questions=[q1])
        applicable = compose_template_questions(template, assessment_mode="full", asset_type_id=None)
        assert applicable == {101}
