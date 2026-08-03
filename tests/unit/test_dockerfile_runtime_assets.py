"""Guards for data files required by runtime and migration code."""

from __future__ import annotations

from pathlib import Path


DOCKERFILE = Path("Dockerfile")


def test_production_image_includes_compliance_schedule_catalogue() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert (
        "COPY --chown=appuser:appgroup "
        "specs/compliance-schedule/catalogue.json "
        "./specs/compliance-schedule/catalogue.json"
    ) in text
