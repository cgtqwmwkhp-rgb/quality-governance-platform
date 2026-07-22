"""Unit tests for essential/required criticality gating in AuditService.

Covers:
- ``_missing_required_question_ids`` composition + conditional-logic skips and
  the essential/required criticality gate.
- ``_has_failed_essential_question`` mandatory-pass override used by
  ``complete_run`` to fail a run even when the weighted score clears
  threshold.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.domain.services.audit_service import AuditService


def _question(
    id_,
    *,
    is_active=True,
    is_required=True,
    criticality=None,
    section_id=None,
    question_type="yes_no",
    positive_answer="yes",
    options_json=None,
    evidence_requirements_json=None,
    conditional_logic_json=None,
    risk_weight=None,
):
    return SimpleNamespace(
        id=id_,
        is_active=is_active,
        is_required=is_required,
        criticality=criticality,
        section_id=section_id,
        question_type=question_type,
        positive_answer=positive_answer,
        options_json=options_json,
        evidence_requirements_json=evidence_requirements_json,
        conditional_logic_json=conditional_logic_json,
        risk_weight=risk_weight,
    )


def _response(question_id, *, response_value=None, is_na=False, applicability=None, response_json=None):
    return SimpleNamespace(
        question_id=question_id,
        response_value=response_value,
        response_text=None,
        response_number=None,
        response_bool=None,
        response_date=None,
        response_json=response_json,
        is_na=is_na,
        applicability=applicability,
    )


def _section(id_, rules=None):
    return SimpleNamespace(id=id_, applicability_rules_json=rules)


class TestMissingRequiredQuestionIds:
    def test_essential_criticality_is_required_even_when_is_required_false(self):
        questions = [_question(1, is_required=False, criticality="essential")]
        missing = AuditService._missing_required_question_ids(questions=questions, responses=[])
        assert missing == [1]

    def test_required_criticality_is_required_even_when_is_required_false(self):
        questions = [_question(1, is_required=False, criticality="required")]
        missing = AuditService._missing_required_question_ids(questions=questions, responses=[])
        assert missing == [1]

    def test_good_to_have_never_blocks_when_not_explicitly_required(self):
        questions = [_question(1, is_required=False, criticality="good_to_have")]
        missing = AuditService._missing_required_question_ids(questions=questions, responses=[])
        assert missing == []

    def test_composition_skips_out_of_scope_section(self):
        section = _section(1, rules={"assessment_modes": ["full"]})
        questions = [_question(1, criticality="essential", section_id=1)]
        missing = AuditService._missing_required_question_ids(
            questions=questions,
            responses=[],
            sections=[section],
            assessment_mode="spot_check",
            asset_type_id=None,
        )
        assert missing == []

        missing_when_applicable = AuditService._missing_required_question_ids(
            questions=questions,
            responses=[],
            sections=[section],
            assessment_mode="full",
            asset_type_id=None,
        )
        assert missing_when_applicable == [1]

    def test_hidden_by_logic_response_is_skipped(self):
        questions = [_question(1, criticality="essential")]
        responses = [_response(1, applicability="hidden_by_logic")]
        missing = AuditService._missing_required_question_ids(questions=questions, responses=responses)
        assert missing == []

    def test_conditional_logic_hides_question_from_live_answers(self):
        # Q2 only shows when Q1 == "yes"; Q1 answered "no" -> Q2 not required.
        q1 = _question(1, criticality="required", question_type="yes_no")
        q2 = _question(
            2,
            criticality="essential",
            conditional_logic_json=[{"source_question_id": 1, "operator": "equals", "value": "yes", "action": "show"}],
        )
        responses = [_response(1, response_value="no")]
        missing = AuditService._missing_required_question_ids(questions=[q1, q2], responses=responses)
        assert missing == []

        responses_shown = [_response(1, response_value="yes")]
        missing_shown = AuditService._missing_required_question_ids(questions=[q1, q2], responses=responses_shown)
        assert missing_shown == [2]


class TestHasFailedEssentialQuestion:
    def test_failed_essential_pass_fail_question_detected(self):
        question = _question(1, criticality="essential", question_type="pass_fail", positive_answer="yes")
        responses = [_response(1, response_value="fail")]
        assert AuditService._has_failed_essential_question([question], responses) is True

    def test_passed_essential_question_is_not_flagged(self):
        question = _question(1, criticality="essential", question_type="pass_fail", positive_answer="yes")
        responses = [_response(1, response_value="pass")]
        assert AuditService._has_failed_essential_question([question], responses) is False

    def test_non_essential_failure_does_not_trigger_gate(self):
        question = _question(1, criticality="required", question_type="pass_fail", positive_answer="yes")
        responses = [_response(1, response_value="fail")]
        assert AuditService._has_failed_essential_question([question], responses) is False

    def test_unanswered_essential_question_does_not_trigger_gate(self):
        question = _question(1, criticality="essential", question_type="pass_fail")
        assert AuditService._has_failed_essential_question([question], []) is False

    def test_hidden_by_logic_essential_failure_is_ignored(self):
        question = _question(1, criticality="essential", question_type="pass_fail")
        responses = [_response(1, response_value="fail", applicability="hidden_by_logic")]
        assert AuditService._has_failed_essential_question([question], responses) is False

    def test_out_of_composition_scope_essential_failure_is_ignored(self):
        section = _section(1, rules={"asset_type_ids": [5]})
        question = _question(1, criticality="essential", question_type="pass_fail", section_id=1)
        responses = [_response(1, response_value="fail")]
        assert (
            AuditService._has_failed_essential_question([question], responses, sections=[section], asset_type_id=9)
            is False
        )
        assert (
            AuditService._has_failed_essential_question([question], responses, sections=[section], asset_type_id=5)
            is True
        )
