"""Conditional show/hide logic evaluator for audit questions.

Rule shape (mirrors ``ConditionalLogicRule`` in ``src/api/schemas/audit.py``
and the FE mirror in ``frontend/src/pages/audit-builder/evaluateConditionalLogic.ts``)::

    {
        "source_question_id": <int|str>,
        "operator": "equals" | "not_equals" | "contains" | "greater_than" |
                     "less_than" | "is_empty" | "is_not_empty",
        "value": <any>,
        "action": "show" | "hide",
    }

A question with no rules is always visible. When multiple rules are present,
each is evaluated independently and combined with AND semantics: a "show"
rule that doesn't match hides the question; a "hide" rule that matches hides
the question. In other words, all rules must "pass" (i.e. not block
visibility) for the question to be visible.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

_VISIBILITY_ACTIONS = {"show", "hide"}


def _coerce_key(value: Any) -> str:
    return str(value)


def _get_answer_value(answers: Mapping[Any, Any], question_id: Any) -> Any:
    """Look up an answer by question id, tolerating int/str key mismatches."""
    if question_id in answers:
        return answers[question_id]
    key = _coerce_key(question_id)
    if key in answers:
        return answers[key]
    try:
        numeric_key = int(key)
    except (TypeError, ValueError):
        numeric_key = None
    if numeric_key is not None and numeric_key in answers:
        return answers[numeric_key]
    return None


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _as_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _values_match(answer: Any, expected: Any) -> bool:
    if answer is None:
        return expected is None
    if isinstance(answer, bool) or isinstance(expected, bool):
        return bool(answer) == bool(expected)
    answer_num = _as_number(answer)
    expected_num = _as_number(expected)
    if answer_num is not None and expected_num is not None:
        return answer_num == expected_num
    return str(answer).strip().lower() == str(expected).strip().lower()


def _contains(answer: Any, expected: Any) -> bool:
    if isinstance(answer, (list, tuple, set)):
        return any(_values_match(item, expected) for item in answer)
    if answer is None:
        return False
    return str(expected).strip().lower() in str(answer).strip().lower()


def evaluate_rule(rule: Mapping[str, Any], answers: Mapping[Any, Any]) -> bool:
    """Return True when *rule*'s condition is satisfied by *answers*."""
    source_id = rule.get("source_question_id")
    operator = rule.get("operator")
    expected = rule.get("value")
    answer = _get_answer_value(answers, source_id)

    if operator == "is_empty":
        return _is_empty(answer)
    if operator == "is_not_empty":
        return not _is_empty(answer)
    if operator == "equals":
        return _values_match(answer, expected)
    if operator == "not_equals":
        return not _values_match(answer, expected)
    if operator == "contains":
        return _contains(answer, expected)
    if operator == "greater_than":
        answer_num, expected_num = _as_number(answer), _as_number(expected)
        if answer_num is None or expected_num is None:
            return False
        return answer_num > expected_num
    if operator == "less_than":
        answer_num, expected_num = _as_number(answer), _as_number(expected)
        if answer_num is None or expected_num is None:
            return False
        return answer_num < expected_num
    # Unknown operator: fail open (rule does not block visibility).
    return True


def is_question_visible(
    rules: Optional[Sequence[Mapping[str, Any]]],
    answers: Mapping[Any, Any],
) -> bool:
    """Evaluate a question's ``conditional_logic_json`` rule array.

    Rules with an ``action`` other than ``show``/``hide`` are ignored (no-op)
    so legacy ``require``/``skip`` rows don't unexpectedly hide questions.
    """
    if not rules:
        return True

    visible = True
    for rule in rules:
        if not isinstance(rule, Mapping):
            continue
        action = rule.get("action")
        if action not in _VISIBILITY_ACTIONS:
            continue
        matched = evaluate_rule(rule, answers)
        if action == "show" and not matched:
            visible = False
        elif action == "hide" and matched:
            visible = False
    return visible


def filter_visible_question_ids(
    questions: Sequence[Any],
    answers: Mapping[Any, Any],
    *,
    rules_attr: str = "conditional_logic_json",
) -> set:
    """Return the ids of *questions* that are visible given current *answers*."""
    visible_ids: set = set()
    for question in questions:
        rules = getattr(question, rules_attr, None)
        if is_question_visible(rules, answers):
            visible_ids.add(question.id)
    return visible_ids
