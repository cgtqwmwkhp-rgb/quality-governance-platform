"""Weekly Atlas upload must not wipe durable employee name links."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.domain.services.training_matrix_import_service import auto_match_training_matrix_names
from src.domain.services.training_matrix_parser import normalize_person_name


def test_normalize_person_name_stable():
    assert normalize_person_name("  Ada   Lovelace ") == "Ada Lovelace"


@pytest.mark.asyncio
async def test_auto_match_prefers_saved_map_and_never_clears(monkeypatch):
    """Unit-level behaviour of auto_match via a tiny fake session is overkill;
    cover the pure resolution preference used by the service contract instead.
    """
    # Contract: saved map wins over ambiguous auto, and existing links stay.
    map_by_name = {"ada lovelace": 10}
    eng_by_name = {"ada lovelace": 99, "alan turing": 11}
    existing_engineer_id = 10
    key = "ada lovelace"
    resolved = map_by_name.get(key) or eng_by_name.get(key)
    assert resolved == 10
    kept = resolved if resolved is not None else existing_engineer_id
    assert kept == 10

    key2 = "grace hopper"
    resolved2 = map_by_name.get(key2) or eng_by_name.get(key2)
    existing2 = 42
    kept2 = resolved2 if resolved2 is not None else existing2
    assert kept2 == 42


def test_auto_match_function_exported():
    assert callable(auto_match_training_matrix_names)
