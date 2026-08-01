"""B-10 high-traffic completion batch: unknown body fields must raise (extra=forbid)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.routes.ai_intelligence import FiveWhysRequest
from src.api.routes.ai_templates import (
    ChallengeDecideRequest,
    ChallengeMessageRequest,
    ChallengeSessionCreateRequest,
    ConvertToAssessmentRequest,
)
from src.api.routes.capa import CAPACreate, CAPAUpdate
from src.api.routes.governed_knowledge import BulkConfirmRequest
from src.api.routes.planet_mark import BulkStatusUpdate
from src.api.schemas.auth import LoginRequest, PasswordChangeRequest, PasswordResetConfirm, PasswordResetRequest
from src.api.schemas.engineer import (
    CompetencyRequirementAllocateRequest,
    CompetencyRequirementCreate,
    CompetencyRequirementUpdate,
)
from src.domain.models.capa import CAPAPriority, CAPAType


def _assert_rejects_unknown(factory, **kwargs) -> None:
    with pytest.raises(ValidationError) as exc_info:
        factory(**kwargs, tenant_id=1)  # type: ignore[call-arg]
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()


def test_login_request_forbid() -> None:
    m = LoginRequest(email="user@example.com", password="secret")
    assert m.email == "user@example.com"
    _assert_rejects_unknown(LoginRequest, email="user@example.com", password="secret")


def test_password_change_forbid() -> None:
    m = PasswordChangeRequest(current_password="old-secret", new_password="new-secret1")
    assert m.new_password.startswith("new")
    _assert_rejects_unknown(PasswordChangeRequest, current_password="old-secret", new_password="new-secret1")


def test_password_reset_request_forbid() -> None:
    m = PasswordResetRequest(email="user@example.com")
    assert str(m.email) == "user@example.com"
    _assert_rejects_unknown(PasswordResetRequest, email="user@example.com")


def test_password_reset_confirm_forbid() -> None:
    m = PasswordResetConfirm(token="abc", new_password="new-secret1")
    assert m.token == "abc"
    _assert_rejects_unknown(PasswordResetConfirm, token="abc", new_password="new-secret1")


def test_challenge_session_create_forbid() -> None:
    m = ChallengeSessionCreateRequest(sections=[{"title": "A"}])
    assert len(m.sections) == 1
    _assert_rejects_unknown(ChallengeSessionCreateRequest, sections=[{"title": "A"}])


def test_challenge_message_forbid() -> None:
    m = ChallengeMessageRequest(message="Tighten the control wording")
    assert "Tighten" in m.message
    _assert_rejects_unknown(ChallengeMessageRequest, message="Tighten the control wording")


def test_challenge_decide_forbid() -> None:
    m = ChallengeDecideRequest(decision="accept")
    assert m.decision == "accept"
    _assert_rejects_unknown(ChallengeDecideRequest, decision="accept")


def test_convert_to_assessment_forbid() -> None:
    m = ConvertToAssessmentRequest(template={"name": "T"})
    assert m.template["name"] == "T"
    _assert_rejects_unknown(ConvertToAssessmentRequest, template={"name": "T"})


def test_capa_create_forbid() -> None:
    m = CAPACreate(title="Fix guardrail", capa_type=CAPAType.CORRECTIVE)
    assert m.title.startswith("Fix")
    _assert_rejects_unknown(CAPACreate, title="Fix guardrail", capa_type=CAPAType.CORRECTIVE)


def test_capa_update_forbid() -> None:
    m = CAPAUpdate(title="Updated title", priority=CAPAPriority.HIGH)
    assert m.priority == CAPAPriority.HIGH
    _assert_rejects_unknown(CAPAUpdate, title="Updated title")


def test_five_whys_forbid() -> None:
    m = FiveWhysRequest(incident_id=1, answers=["why1"])
    assert m.incident_id == 1
    _assert_rejects_unknown(FiveWhysRequest, incident_id=1, answers=["why1"])


def test_competency_requirement_create_forbid() -> None:
    m = CompetencyRequirementCreate(asset_type_id=1, template_id=2, name="Working at height")
    assert m.name.startswith("Working")
    _assert_rejects_unknown(CompetencyRequirementCreate, asset_type_id=1, template_id=2, name="Working at height")


def test_competency_requirement_update_forbid() -> None:
    m = CompetencyRequirementUpdate(name="Updated competency")
    assert m.name.startswith("Updated")
    _assert_rejects_unknown(CompetencyRequirementUpdate, name="Updated competency")


def test_competency_requirement_allocate_forbid() -> None:
    m = CompetencyRequirementAllocateRequest(engineer_ids=[1, 2])
    assert m.engineer_ids == [1, 2]
    _assert_rejects_unknown(CompetencyRequirementAllocateRequest, engineer_ids=[1, 2])


def test_bulk_confirm_forbid() -> None:
    m = BulkConfirmRequest(link_ids=[1, 2])
    assert m.link_ids == [1, 2]
    _assert_rejects_unknown(BulkConfirmRequest, link_ids=[1, 2])


def test_bulk_status_update_forbid() -> None:
    m = BulkStatusUpdate(action_ids=[1], status="closed")
    assert m.status == "closed"
    _assert_rejects_unknown(BulkStatusUpdate, action_ids=[1], status="closed")
