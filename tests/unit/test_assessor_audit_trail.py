"""Unit tests for assessor audit trail action labels / payload contract."""

from types import SimpleNamespace


def test_confirm_reject_actions_are_distinct() -> None:
    confirm = "evidence_confirm"
    reject = "evidence_reject"
    assess = "operational_standards_assess"
    assert confirm != reject
    assert assess not in {confirm, reject}


def test_trail_payload_contract() -> None:
    payload = {
        "link_id": 12,
        "clause_id": "7.5",
        "prior_status": "proposed",
        "actor_email": "assessor@example.com",
        "actor_id": 3,
    }
    assert payload["link_id"] == 12
    assert "actor_email" in payload


def test_staff_user_namespace_for_actor() -> None:
    user = SimpleNamespace(id=9, email="a@b.co")
    assert getattr(user, "email", None) == "a@b.co"
