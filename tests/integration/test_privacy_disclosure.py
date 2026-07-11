"""Unit tests for public privacy contact + security.txt (Path-to-10 S15)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_privacy_contact_public(client: AsyncClient):
    response = await client.get("/api/v1/privacy/contact")

    assert response.status_code == 200
    data = response.json()
    assert "privacy_contact" in data
    assert "security_contact" in data
    assert data["security_txt"] == "/.well-known/security.txt"
    assert data["data_lifecycle"]["soft_delete"] is True
    assert data["data_lifecycle"]["evidence_legal_hold"] is True
    assert "ocr_ai_import" in data["dpia"]
    retention = data["retention"]
    assert retention["soft_delete_first"] is True
    assert retention["matter_level_legal_hold_schema"] is False
    assert retention["policy_doc"] == "docs/privacy/data-retention-policy.md"
    assert retention["entity_horizons_days"]["incidents"] == 2555
    assert retention["entity_horizons_days"]["session_logs"] == 90


@pytest.mark.asyncio
async def test_well_known_security_txt(client: AsyncClient):
    response = await client.get("/.well-known/security.txt")

    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    body = response.text
    assert "Contact:" in body
    assert "Preferred-Languages: en" in body
    assert "Canonical:" in body
