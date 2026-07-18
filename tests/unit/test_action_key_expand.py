"""Bare numeric action_key expansion for /actions/{id} UAT deep-links."""

from src.api.routes._action_unified import (
    STORAGE_CAPA,
    STORAGE_INCIDENT_ACTION,
    expand_action_key_candidates,
)


def test_expand_stable_action_key_unchanged():
    assert expand_action_key_candidates("capa:12") == ["capa:12"]
    assert expand_action_key_candidates("incident_action:2") == ["incident_action:2"]


def test_expand_bare_numeric_prefers_incident_then_capa():
    keys = expand_action_key_candidates("2")
    assert keys[0] == f"{STORAGE_INCIDENT_ACTION}:2"
    assert f"{STORAGE_CAPA}:2" in keys
    assert keys == list(dict.fromkeys(keys))


def test_expand_empty_key():
    assert expand_action_key_candidates("") == []
    assert expand_action_key_candidates("   ") == []
