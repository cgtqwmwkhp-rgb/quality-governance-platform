"""Customer Feedback kind policy (FB-PR2).

Kind is the discriminator. Prefix, transitions, close gates, and the write
flag all hang off it. Polarity stays derived in the model — never stored.
"""

from __future__ import annotations

from src.domain.exceptions import ValidationError
from src.domain.models.complaint import ComplaintStatus, FeedbackKind

KIND_RECORD_TYPE: dict[FeedbackKind, str] = {
    FeedbackKind.COMPLAINT: "complaint",
    FeedbackKind.COMPLIMENT: "compliment",
    FeedbackKind.SUGGESTION: "suggestion",
    FeedbackKind.GENERAL: "general",
}

LIGHT_CLOSE_KINDS: frozenset[FeedbackKind] = frozenset({FeedbackKind.COMPLIMENT, FeedbackKind.GENERAL})

COMPLIMENT_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    ComplaintStatus.RECEIVED: {ComplaintStatus.ACKNOWLEDGED},
    ComplaintStatus.ACKNOWLEDGED: {ComplaintStatus.CLOSED},
    ComplaintStatus.CLOSED: {ComplaintStatus.ACKNOWLEDGED},
}

SUGGESTION_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    ComplaintStatus.RECEIVED: {ComplaintStatus.ACKNOWLEDGED, ComplaintStatus.ESCALATED},
    ComplaintStatus.ACKNOWLEDGED: {ComplaintStatus.UNDER_INVESTIGATION, ComplaintStatus.CLOSED},
    ComplaintStatus.UNDER_INVESTIGATION: {ComplaintStatus.CLOSED, ComplaintStatus.ESCALATED},
    ComplaintStatus.ESCALATED: {ComplaintStatus.UNDER_INVESTIGATION, ComplaintStatus.CLOSED},
    ComplaintStatus.CLOSED: {ComplaintStatus.UNDER_INVESTIGATION},
}

GENERAL_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    ComplaintStatus.RECEIVED: {ComplaintStatus.ACKNOWLEDGED, ComplaintStatus.CLOSED},
    ComplaintStatus.ACKNOWLEDGED: {ComplaintStatus.CLOSED},
    ComplaintStatus.CLOSED: {ComplaintStatus.ACKNOWLEDGED},
}


def parse_feedback_kind(value) -> FeedbackKind:
    if isinstance(value, FeedbackKind):
        return value
    if not isinstance(value, str) or not value.strip():
        return FeedbackKind.COMPLAINT
    try:
        return FeedbackKind(value.strip().lower())
    except ValueError as exc:
        raise ValidationError(f"Invalid feedback_kind '{value}'") from exc


def kinds_write_enabled() -> bool:
    from src.core.config import settings

    return bool(getattr(settings, "customer_feedback_kinds_enabled", False))


def assert_kind_may_be_written(kind: FeedbackKind) -> None:
    """PR-5 flips the flag. Until then only complaint may be created."""
    if kind is FeedbackKind.COMPLAINT:
        return
    if kinds_write_enabled():
        return
    raise ValidationError(
        "feedback_kind other than complaint is disabled until customer_feedback_kinds is on",
        details={"feedback_kind": kind.value, "flag": "customer_feedback_kinds"},
    )


def assert_compliment_has_subject(*, subject_user_id, subject_name: str | None) -> None:
    named = (subject_name or "").strip()
    if subject_user_id is not None or named:
        return
    raise ValidationError(
        "A compliment must name the staff member it is about",
        details={"field": "subject_name"},
    )


def transitions_for(kind: FeedbackKind) -> dict[ComplaintStatus, set[ComplaintStatus]]:
    from src.domain.services.complaint_service import COMPLAINT_TRANSITIONS

    if kind is FeedbackKind.COMPLIMENT:
        return COMPLIMENT_TRANSITIONS
    if kind is FeedbackKind.SUGGESTION:
        return SUGGESTION_TRANSITIONS
    if kind is FeedbackKind.GENERAL:
        return GENERAL_TRANSITIONS
    return COMPLAINT_TRANSITIONS


def lessons_required_for(kind: FeedbackKind) -> bool:
    return kind not in LIGHT_CLOSE_KINDS
