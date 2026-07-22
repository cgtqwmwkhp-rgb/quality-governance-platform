"""Unit tests for the conditional show/hide evaluator (audit_conditional.py)."""

from __future__ import annotations

from types import SimpleNamespace

from src.domain.services.audit_conditional import (
    evaluate_rule,
    filter_visible_question_ids,
    is_question_visible,
)


class TestEvaluateRule:
    def test_equals_matches_case_insensitively(self):
        rule = {"source_question_id": 1, "operator": "equals", "value": "Yes", "action": "show"}
        assert evaluate_rule(rule, {1: "yes"}) is True
        assert evaluate_rule(rule, {1: "no"}) is False

    def test_not_equals(self):
        rule = {"source_question_id": 1, "operator": "not_equals", "value": "yes", "action": "hide"}
        assert evaluate_rule(rule, {1: "no"}) is True
        assert evaluate_rule(rule, {1: "yes"}) is False

    def test_contains_on_list_answer(self):
        rule = {"source_question_id": 2, "operator": "contains", "value": "electrical", "action": "show"}
        assert evaluate_rule(rule, {2: ["mechanical", "electrical"]}) is True
        assert evaluate_rule(rule, {2: ["mechanical"]}) is False

    def test_contains_on_string_answer(self):
        rule = {"source_question_id": 2, "operator": "contains", "value": "fail", "action": "show"}
        assert evaluate_rule(rule, {2: "partial failure noted"}) is True

    def test_greater_than_and_less_than_numeric(self):
        gt_rule = {"source_question_id": 3, "operator": "greater_than", "value": 5, "action": "show"}
        lt_rule = {"source_question_id": 3, "operator": "less_than", "value": 5, "action": "show"}
        assert evaluate_rule(gt_rule, {3: 10}) is True
        assert evaluate_rule(gt_rule, {3: 2}) is False
        assert evaluate_rule(lt_rule, {3: 2}) is True

    def test_is_empty_and_is_not_empty(self):
        empty_rule = {"source_question_id": 4, "operator": "is_empty", "action": "hide"}
        not_empty_rule = {"source_question_id": 4, "operator": "is_not_empty", "action": "show"}
        assert evaluate_rule(empty_rule, {4: ""}) is True
        assert evaluate_rule(empty_rule, {4: None}) is True
        assert evaluate_rule(empty_rule, {}) is True
        assert evaluate_rule(not_empty_rule, {4: "value"}) is True
        assert evaluate_rule(not_empty_rule, {4: ""}) is False

    def test_string_key_answers_are_tolerated(self):
        rule = {"source_question_id": 1, "operator": "equals", "value": "yes", "action": "show"}
        assert evaluate_rule(rule, {"1": "yes"}) is True

    def test_unknown_operator_fails_open(self):
        rule = {"source_question_id": 1, "operator": "bogus", "value": "x", "action": "show"}
        assert evaluate_rule(rule, {1: "anything"}) is True


class TestIsQuestionVisible:
    def test_no_rules_is_visible(self):
        assert is_question_visible(None, {}) is True
        assert is_question_visible([], {}) is True

    def test_show_rule_hides_when_condition_not_met(self):
        rules = [{"source_question_id": 1, "operator": "equals", "value": "yes", "action": "show"}]
        assert is_question_visible(rules, {1: "yes"}) is True
        assert is_question_visible(rules, {1: "no"}) is False

    def test_hide_rule_hides_when_condition_met(self):
        rules = [{"source_question_id": 1, "operator": "equals", "value": "no", "action": "hide"}]
        assert is_question_visible(rules, {1: "no"}) is False
        assert is_question_visible(rules, {1: "yes"}) is True

    def test_multiple_rules_combine_with_and_semantics(self):
        rules = [
            {"source_question_id": 1, "operator": "equals", "value": "yes", "action": "show"},
            {"source_question_id": 2, "operator": "equals", "value": "critical", "action": "hide"},
        ]
        assert is_question_visible(rules, {1: "yes", 2: "minor"}) is True
        assert is_question_visible(rules, {1: "no", 2: "minor"}) is False
        assert is_question_visible(rules, {1: "yes", 2: "critical"}) is False

    def test_non_visibility_actions_are_ignored(self):
        rules = [{"source_question_id": 1, "operator": "equals", "value": "yes", "action": "require"}]
        assert is_question_visible(rules, {1: "no"}) is True

    def test_malformed_rule_entries_are_skipped(self):
        rules = ["not-a-dict", {"source_question_id": 1, "operator": "equals", "value": "yes", "action": "show"}]
        assert is_question_visible(rules, {1: "yes"}) is True


class TestFilterVisibleQuestionIds:
    def test_filters_by_rules_attribute(self):
        questions = [
            SimpleNamespace(id=1, conditional_logic_json=None),
            SimpleNamespace(
                id=2,
                conditional_logic_json=[
                    {"source_question_id": 1, "operator": "equals", "value": "yes", "action": "show"}
                ],
            ),
        ]
        assert filter_visible_question_ids(questions, {1: "no"}) == {1}
        assert filter_visible_question_ids(questions, {1: "yes"}) == {1, 2}
