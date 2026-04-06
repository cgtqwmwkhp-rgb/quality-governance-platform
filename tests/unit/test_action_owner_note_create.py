"""Schema validation for action owner note create payload."""

import pytest
from pydantic import ValidationError

from src.api.routes.actions import ActionOwnerNoteCreate


def test_action_owner_note_create_strips_key_and_body() -> None:
    m = ActionOwnerNoteCreate(key="  capa:1  ", body="  hello  ")
    assert m.key == "capa:1"
    assert m.body == "hello"


def test_action_owner_note_create_rejects_whitespace_only_body() -> None:
    with pytest.raises(ValidationError):
        ActionOwnerNoteCreate(key="capa:1", body="   \n\t  ")


def test_action_owner_note_create_rejects_short_key_after_strip() -> None:
    with pytest.raises(ValidationError):
        ActionOwnerNoteCreate(key="  x  ", body="valid body text here")
