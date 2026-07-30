"""Guard: production image must not ship pip (Trivy flags pip-vendored advisories)."""

from __future__ import annotations

from pathlib import Path

DOCKERFILE = Path("Dockerfile")


def test_builder_uninstalls_pip_before_production_copy() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "pip uninstall -y pip" in text
    # Builder stage must clear venv pip before the production COPY of /opt/venv.
    builder, _, production = text.partition("AS production")
    assert "pip uninstall -y pip" in builder
    assert "/opt/venv/lib/python3.11/site-packages/pip" in builder
    assert "pip uninstall -y pip" in production
    assert "/usr/local/lib/python3.11/site-packages/pip" in production


def test_dockerfile_documents_trivy_vendor_reason() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "GHSA-6v7p-g79w-8964" in text
    assert "CVE-2025-47273" in text
