"""GET builder payload must hide soft-deleted leftover sections/questions."""

from __future__ import annotations

from datetime import datetime, timezone

from src.api.schemas.audit import (
    AuditQuestionResponse,
    AuditSectionResponse,
    AuditTemplateDetailResponse,
    retain_live_template_graph,
)

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _question(*, question_id: int, text: str, active: bool) -> AuditQuestionResponse:
    return AuditQuestionResponse.model_construct(
        id=question_id,
        template_id=28,
        question_text=text,
        question_type="yes_no",
        is_active=active,
        created_at=NOW,
        updated_at=NOW,
    )


def _section(
    *, section_id: int, title: str, active: bool, questions: list[AuditQuestionResponse]
) -> AuditSectionResponse:
    return AuditSectionResponse.model_construct(
        id=section_id,
        template_id=28,
        title=title,
        is_active=active,
        questions=questions,
        created_at=NOW,
        updated_at=NOW,
    )


def test_retain_live_template_graph_drops_wickford_leftovers() -> None:
    live = _question(question_id=12, text="Fire exits clear?", active=True)
    ghost_q = _question(question_id=137, text="Select areas", active=False)
    response = AuditTemplateDetailResponse.model_construct(
        id=28,
        name="Wickford HQ Daily Site Inspection",
        created_at=NOW,
        updated_at=NOW,
        sections=[
            _section(section_id=30, title="Section 1", active=False, questions=[]),
            _section(section_id=4, title="Fire", active=True, questions=[live, ghost_q]),
        ],
        section_count=2,
        question_count=2,
    )

    live_graph = retain_live_template_graph(response)

    assert [section.id for section in live_graph.sections] == [4]
    assert [question.id for question in live_graph.sections[0].questions] == [12]
    assert live_graph.section_count == 1
    assert live_graph.question_count == 1
