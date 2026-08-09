"""Every Doc Graph flag must be written by the governed deploy path (WE-1).

``az webapp config appsettings set`` merges, so a flag someone set by hand in the
portal survives deploy after deploy and looks durable. It is not: it exists in no
repository file, no repo variable and no workflow, so a reprovision or a settings
replacement drops it silently and the surface changes with nothing to point at.

That was true of the four Doc Graph subflags while STG/PROD ran them on: the
master and heuristic flags came from repo variables, the other four were live
app settings only. This test is what keeps every flag on the governed path, and
what stops one being pinned to a literal ``'true'`` instead of a kill switch.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = (
    Path(".github/workflows/deploy-production.yml"),
    Path(".github/workflows/deploy-staging.yml"),
)

# Every DOCUMENT_GRAPH_* setting read by src/core/config.py that has a wired surface.
# IMPACT / LLM propose stay deliberately unwired, so they are not listed here.
DOCUMENT_GRAPH_FLAGS = (
    "DOCUMENT_GRAPH_ENABLED",
    "DOCUMENT_GRAPH_HEURISTIC_PROPOSE_ENABLED",
    "DOCUMENT_GRAPH_THREAD_AMBIENT_ENABLED",
    "DOCUMENT_GRAPH_MAP_VIEW_ENABLED",
    "DOCUMENT_GRAPH_DND_PROPOSE_ENABLED",
    "DOCUMENT_GRAPH_STRUCTURE_MAP_ENABLED",
)


def _assignments(text: str, flag: str) -> list[str]:
    return re.findall(rf'{re.escape(flag)}="([^"]*)"', text)


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
@pytest.mark.parametrize("flag", DOCUMENT_GRAPH_FLAGS)
def test_deploy_writes_every_doc_graph_flag(workflow: Path, flag: str) -> None:
    assignments = _assignments(workflow.read_text(), flag)
    assert assignments, (
        f"{workflow.name}: {flag} is never written by the deploy. A hand-set Azure app "
        "setting is not durable — declare it here so the repo variable owns it."
    )


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
@pytest.mark.parametrize("flag", DOCUMENT_GRAPH_FLAGS)
def test_doc_graph_flags_come_from_a_repo_variable_and_default_closed(workflow: Path, flag: str) -> None:
    """Default-off keeps the flag a kill switch; a literal would weld it open."""
    expected = "${{ vars." + flag + " || 'false' }}"
    for assignment in _assignments(workflow.read_text(), flag):
        assert assignment == expected, (
            f"{workflow.name}: {flag} is assigned {assignment!r} rather than {expected!r}. "
            "Doc Graph flags must resolve from their repo variable and default closed."
        )


@pytest.mark.parametrize("flag", DOCUMENT_GRAPH_FLAGS)
def test_doc_graph_flags_are_registered_for_operators(flag: str) -> None:
    """A flag nobody documented is a flag nobody can find when a surface misbehaves."""
    import json

    registry = json.loads(Path("scripts/infra/env-vars.json").read_text())
    assert flag in registry, f"{flag} missing from scripts/infra/env-vars.json"
    assert registry[flag]["default"] == "false", f"{flag} must be registered as default false"

    env_example = Path(".env.example").read_text()
    assert f"{flag}=false" in env_example, f"{flag} missing (or not default false) in .env.example"


@pytest.mark.parametrize("flag", DOCUMENT_GRAPH_FLAGS)
def test_every_deployed_flag_has_a_settings_field(flag: str) -> None:
    """The workflow key must match the field the app actually reads."""
    from src.core.config import settings

    attr = flag.lower()
    assert hasattr(settings, attr), f"{flag} has no matching settings field '{attr}'"
    assert getattr(settings, attr) in (True, False)
