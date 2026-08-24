"""Customer Feedback PR-1 — discriminator honesty."""

from datetime import datetime, timezone
from pathlib import Path

from src.api.schemas.complaint import ComplaintCreate, ComplaintResponse, ComplaintUpdate
from src.domain.models.complaint import (
    FEEDBACK_POLARITY,
    ComplaintPriority,
    ComplaintType,
    FeedbackKind,
    FeedbackPolarity,
)
from src.domain.services.lookup_defaults_seed_data import rows_for_category


def test_polarity_map_covers_every_kind() -> None:
    assert set(FEEDBACK_POLARITY) == set(FeedbackKind)
    assert FEEDBACK_POLARITY[FeedbackKind.COMPLAINT] is FeedbackPolarity.NEGATIVE
    assert FEEDBACK_POLARITY[FeedbackKind.COMPLIMENT] is FeedbackPolarity.POSITIVE
    assert FEEDBACK_POLARITY[FeedbackKind.SUGGESTION] is FeedbackPolarity.NEUTRAL
    assert FEEDBACK_POLARITY[FeedbackKind.GENERAL] is FeedbackPolarity.NEUTRAL


def test_seeded_feedback_kinds_match_the_enum() -> None:
    seeded = [row.code for row in rows_for_category("feedback_kinds")]
    assert seeded == [kind.value for kind in FeedbackKind]


def test_create_schema_defaults_kind_to_complaint() -> None:
    payload = ComplaintCreate(
        title="Product Defect",
        description="The product arrived broken.",
        complaint_type=ComplaintType.PRODUCT,
        priority=ComplaintPriority.HIGH,
        received_date=datetime.now(timezone.utc),
        complainant_name="John Doe",
    )
    dumped = payload.model_dump()
    assert dumped["feedback_kind"] is FeedbackKind.COMPLAINT
    assert "feedback_polarity" not in dumped


def test_response_defaults_to_complaint_and_negative_polarity() -> None:
    received = datetime(2026, 8, 24, tzinfo=timezone.utc)
    response = ComplaintResponse.model_validate(
        {
            "id": 1,
            "reference_number": "COMP-2026-0001",
            "title": "Late repairs",
            "description": "Nobody called back.",
            "complaint_type": ComplaintType.SERVICE,
            "priority": ComplaintPriority.HIGH,
            "received_date": received,
            "complainant_name": "Jo Bloggs",
            "status": "received",
            "created_at": received,
            "updated_at": received,
        }
    )
    assert response.feedback_kind is FeedbackKind.COMPLAINT
    assert response.feedback_polarity is FeedbackPolarity.NEGATIVE


def test_response_derives_positive_polarity_from_compliment() -> None:
    received = datetime(2026, 8, 24, tzinfo=timezone.utc)
    response = ComplaintResponse.model_validate(
        {
            "id": 2,
            "reference_number": "CMND-2026-0001",
            "title": "Excellent service",
            "description": "The fitter was outstanding.",
            "complaint_type": ComplaintType.SERVICE,
            "feedback_kind": FeedbackKind.COMPLIMENT,
            "priority": ComplaintPriority.LOW,
            "received_date": received,
            "complainant_name": "Jo Bloggs",
            "status": "received",
            "created_at": received,
            "updated_at": received,
        }
    )
    assert response.feedback_kind is FeedbackKind.COMPLIMENT
    assert response.feedback_polarity is FeedbackPolarity.POSITIVE


def test_create_accepts_kind_on_the_write_path() -> None:
    payload = ComplaintCreate.model_validate(
        {
            "title": "Excellent service",
            "description": "The fitter was outstanding.",
            "complaint_type": ComplaintType.SERVICE,
            "priority": ComplaintPriority.LOW,
            "received_date": datetime.now(timezone.utc),
            "complainant_name": "Jo Bloggs",
            "feedback_kind": "compliment",
        }
    )
    assert payload.feedback_kind is FeedbackKind.COMPLIMENT
    dumped = payload.model_dump()
    assert dumped["feedback_kind"] is FeedbackKind.COMPLIMENT
    assert "feedback_polarity" not in dumped


def test_update_schema_accepts_kind_but_not_polarity() -> None:
    dumped = ComplaintUpdate(title="Still a complaint", feedback_kind=FeedbackKind.SUGGESTION).model_dump(
        exclude_unset=True
    )
    assert dumped["feedback_kind"] is FeedbackKind.SUGGESTION
    assert "feedback_polarity" not in dumped


def test_suggestion_and_general_are_neutral() -> None:
    received = datetime(2026, 8, 24, tzinfo=timezone.utc)
    for kind in (FeedbackKind.SUGGESTION, FeedbackKind.GENERAL):
        response = ComplaintResponse.model_validate(
            {
                "id": 3,
                "reference_number": "SUGG-2026-0001",
                "title": "Could you add evening slots?",
                "description": "Evenings would help.",
                "complaint_type": ComplaintType.SERVICE,
                "feedback_kind": kind,
                "priority": ComplaintPriority.LOW,
                "received_date": received,
                "complainant_name": "Jo Bloggs",
                "status": "received",
                "created_at": received,
                "updated_at": received,
            }
        )
        assert response.feedback_polarity is FeedbackPolarity.NEUTRAL
        assert FEEDBACK_POLARITY[kind] is FeedbackPolarity.NEUTRAL


def test_migration_revises_the_int_w6_head() -> None:
    text = (Path(__file__).resolve().parents[2] / "alembic/versions/20261114_complaint_feedback_kind.py").read_text(
        encoding="utf-8"
    )
    assert 'revision: str = "20261114_cmp_fb_kind"' in text
    assert 'down_revision: Union[str, Sequence[str], None] = "20261113_standards_w6_edges"' in text


def test_flag_defaults_closed() -> None:
    from src.core.config import Settings

    assert Settings.model_fields["customer_feedback_kinds_enabled"].default is False


def test_kind_prefixes_are_independent_of_comp() -> None:
    from src.domain.services.reference_number import ReferenceNumberService

    assert ReferenceNumberService.PREFIXES["complaint"] == "COMP"
    assert ReferenceNumberService.PREFIXES["compliment"] == "CMND"
    assert ReferenceNumberService.PREFIXES["suggestion"] == "SUGG"
    assert ReferenceNumberService.PREFIXES["general"] == "FDBK"


def test_compliment_and_general_close_from_acknowledged() -> None:
    from types import SimpleNamespace

    from src.domain.services.case_closure import CASE_TYPE_COMPLAINT, check_close_transition
    from src.domain.services.complaint_service import validate_complaint_transition

    validate_complaint_transition("acknowledged", "closed", kind="compliment")
    validate_complaint_transition("acknowledged", "closed", kind="general")
    compliment = check_close_transition(
        CASE_TYPE_COMPLAINT, "acknowledged", case=SimpleNamespace(feedback_kind="compliment")
    )
    assert compliment.allowed is True
    complaint = check_close_transition(CASE_TYPE_COMPLAINT, "acknowledged")
    assert complaint.allowed is False


def test_lessons_are_not_required_for_light_kinds() -> None:
    from src.domain.models.complaint import FeedbackKind
    from src.domain.services.feedback_kind_policy import lessons_required_for

    assert lessons_required_for(FeedbackKind.COMPLAINT) is True
    assert lessons_required_for(FeedbackKind.SUGGESTION) is True
    assert lessons_required_for(FeedbackKind.COMPLIMENT) is False
    assert lessons_required_for(FeedbackKind.GENERAL) is False
