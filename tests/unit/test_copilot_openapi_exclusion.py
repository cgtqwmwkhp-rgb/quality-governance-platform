"""PX-248 follow-up: a disabled copilot must not be advertised in the published contract.

The copilot routes stay mounted while ``AI_COPILOT_ENABLED`` is off so their guard can
answer with a stable 404, which means FastAPI would otherwise publish ten paths that no
consumer can call, along with the request/response models of an unreleased feature.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.core.config import settings

COPILOT_PATH_PREFIX = "/api/v1/copilot"
COMPONENT_SCHEMA_REF_PREFIX = "#/components/schemas/"

BASELINE = Path("openapi-baseline.json")
CONTRACT = Path("docs/contracts/openapi.json")

# Models declared in src/api/routes/copilot.py and referenced by nothing else.
COPILOT_ONLY_MODELS = {
    "ActionExecute",
    "FeedbackCreate",
    "MessageCreate",
    "MessageResponse",
    "SessionCreate",
    "SessionResponse",
    "SuggestedAction",
}


@pytest.fixture
def copilot_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ai_copilot_enabled", False)


@pytest.fixture
def copilot_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "app_env", "development")


def _copilot_paths(schema: dict[str, Any]) -> list[str]:
    return [path for path in schema.get("paths", {}) if path.startswith(COPILOT_PATH_PREFIX)]


def _referenced_components(node: Any) -> set[str]:
    """Every component schema name reached by a ``$ref`` inside ``node``."""
    if isinstance(node, dict):
        found = set()
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith(COMPONENT_SCHEMA_REF_PREFIX):
            found.add(ref[len(COMPONENT_SCHEMA_REF_PREFIX) :])
        for value in node.values():
            found |= _referenced_components(value)
        return found
    if isinstance(node, list):
        return set().union(*(_referenced_components(item) for item in node)) if node else set()
    return set()


def test_copilot_paths_are_unpublished_while_disabled(app, copilot_disabled):
    assert _copilot_paths(app.openapi()) == []


def test_copilot_models_are_unpublished_while_disabled(app, copilot_disabled):
    published = set(app.openapi()["components"]["schemas"])

    assert COPILOT_ONLY_MODELS & published == set()


def test_disabled_schema_has_no_dangling_references(app, copilot_disabled):
    """Pruning unpublished models must not orphan a $ref somewhere else in the contract."""
    schema = app.openapi()
    defined = set(schema["components"]["schemas"])

    assert _referenced_components(schema) - defined == set()


def test_copilot_paths_are_published_when_enabled(app, copilot_enabled):
    """The contract must be complete in the state the feature actually ships in."""
    schema = app.openapi()

    assert len(_copilot_paths(schema)) == 10
    assert COPILOT_ONLY_MODELS <= set(schema["components"]["schemas"])
    assert _referenced_components(schema) - set(schema["components"]["schemas"]) == set()


def test_no_published_copilot_operation_is_anonymous(app, copilot_enabled):
    """GET /actions and GET /actions/suggest shipped with no authentication dependency.

    Asserted over every copilot operation rather than those two, so a route added later
    cannot repeat the omission. ``tests/unit/test_copilot_feature_flag.py`` holds the
    tripwire that keeps the mounted surface and the published surface in step.
    """
    anonymous = [
        f"{method.upper()} {path}"
        for path, operations in app.openapi()["paths"].items()
        if path.startswith(COPILOT_PATH_PREFIX)
        for method, operation in operations.items()
        if operation.get("security") != [{"HTTPBearer": []}]
    ]

    assert anonymous == []


@pytest.mark.parametrize("artifact", [BASELINE, CONTRACT])
def test_committed_contract_artifacts_exclude_the_disabled_copilot(artifact: Path):
    schema = json.loads(artifact.read_text(encoding="utf-8"))

    assert _copilot_paths(schema) == []
    assert COPILOT_ONLY_MODELS & set(schema["components"]["schemas"]) == set()
