"""Customer Feedback PR-1 — discriminator honesty."""

from datetime import datetime, timezone

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


def test_create_schema_does_not_accept_a_write_path_for_kind() -> None:
    payload = ComplaintCreate(
        title="Product Defect",
        description="The product arrived broken.",
        complaint_type=ComplaintType.PRODUCT,
        priority=ComplaintPriority.HIGH,
        received_date=datetime.now(timezone.utc),
        complainant_name="John Doe",
    )
    dumped = payload.model_dump()
    assert "feedback_kind" not in dumped


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


def test_create_ignores_kind_in_the_payload() -> None:
    payload = ComplaintCreate.model_validate(
        {
            "title": "Product Defect",
            "description": "The product arrived broken.",
            "complaint_type": ComplaintType.PRODUCT,
            "priority": ComplaintPriority.HIGH,
            "received_date": datetime.now(timezone.utc),
            "complainant_name": "John Doe",
            "feedback_kind": "compliment",
        }
    )
    assert "feedback_kind" not in payload.model_dump()


def test_update_schema_has_no_kind_write_path() -> None:
    dumped = ComplaintUpdate(title="Still a complaint").model_dump(exclude_unset=True)
    assert "feedback_kind" not in dumped
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
