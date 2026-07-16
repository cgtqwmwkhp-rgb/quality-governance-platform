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
    assert data["dpia"]["status"] == "signed"
    assert data["dpia"]["status_doc"] == "docs/compliance/dpia-quality-governance-platform.md"
    assert data["dpia"]["evidence"] == "docs/evidence/dpo-signoff-2026-Q3-READY-FOR-SIGNATURE.md"
    assert data["data_processing_register"] == "/api/v1/privacy/data-processing-register"
    names = {row["name"] for row in data["subprocessors"]}
    assert "Microsoft Azure" in names
    assert "Mistral AI" in names
    assert "Google Gemini" in names
    retention = data["retention"]
    assert retention["soft_delete_first"] is True
    assert retention["matter_level_legal_hold_schema"] is True
    assert retention["matter_level_legal_hold_ssot"] == "matter_legal_holds"
    assert retention["matter_level_legal_hold_api"] == "/api/v1/legal-holds"
    assert retention["matter_level_legal_hold_enforcement"] == "not_yet_wired_to_retention_workers"
    assert retention["policy_doc"] == "docs/privacy/data-retention-policy.md"
    assert retention["entity_horizons_days"]["incidents"] == 2555
    assert retention["entity_horizons_days"]["session_logs"] == 90


@pytest.mark.asyncio
async def test_data_processing_register_stub(client: AsyncClient):
    response = await client.get("/api/v1/privacy/data-processing-register")

    assert response.status_code == 200
    data = response.json()
    assert data["register_kind"] == "article_30_stub"
    assert data["status"] == "stub"
    assert data["dpia"]["status"] == "signed"
    assert data["policy_doc"] == "docs/compliance/gdpr-compliance.md"
    assert len(data["subprocessors"]) >= 3
    activity_ids = {row["activity_id"] for row in data["activities"]}
    assert "incidents" in activity_ids
    assert "ocr-ai-import" in activity_ids
    assert data["contact"] == "/api/v1/privacy/contact"
    assert data["completion_status"] == "structured_platform_scope_pending_privacy_lead_and_controller_review"
    incident = next(row for row in data["activities"] if row["activity_id"] == "incidents")
    assert incident["record_status"] == "platform_scope_documented_pending_controller_review"
    assert incident["controller_ropa_action"] == "confirm_or_complete_in_controller_record"
    assert "docs/compliance/article-30-ropa-checklist.md" in incident["source_documents"]


@pytest.mark.asyncio
async def test_well_known_security_txt(client: AsyncClient):
    response = await client.get("/.well-known/security.txt")

    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    body = response.text
    assert "Contact:" in body
    assert "Preferred-Languages: en" in body
    assert "Canonical:" in body
