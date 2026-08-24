"""Guard: deploy image must ship Library seed specs migrations read at apply time.

WA-2 staging deploy failed because alembic seeds `document_functions` from
`specs/governance-library/functions.json`, but the Dockerfile only copied
`taxonomy.json`. CI runs against a full checkout, so the gap was invisible
until the ACI migration step.
"""

from __future__ import annotations

from pathlib import Path

DOCKERFILE = Path("Dockerfile")


def test_dockerfile_copies_governance_library_seed_specs() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "specs/governance-library/taxonomy.json" in text
    assert "specs/governance-library/functions.json" in text


def test_dockerfile_copies_standards_requirement_axes_spec() -> None:
    """Int-W5 staging failed: alembic loads this JSON, CI checkout hid the gap."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "specs/standards/requirement-axes-v1.json" in text
    assert Path("specs/standards/requirement-axes-v1.json").is_file()


def test_dockerfile_copies_standards_alignment_v11_payload() -> None:
    """Int-W6: import/seed reads this JSON at apply time — same class of W5 miss."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "specs/standards/pel-hseq-5064-alignment-v1.1.json" in text
    assert Path("specs/standards/pel-hseq-5064-alignment-v1.1.json").is_file()


def test_functions_json_exists_in_repo() -> None:
    assert Path("specs/governance-library/functions.json").is_file()
