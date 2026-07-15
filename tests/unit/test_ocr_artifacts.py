"""Unit tests for R5 OCR artifacts, consensus persist hook, and dispute/ack stubs."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.domain.models.ocr_artifact import OCRArtifact, OCRArtifactOverrideStatus, OCRArtifactTier
from src.domain.services.ocr_artifact_service import DEFAULT_PIPELINE_VERSION, OCRArtifactService
from src.domain.services.ocr_consensus import OCRPageCandidate, build_page_consensus, hash_ocr_text
from src.infrastructure.upstream.ai_status import get_ocr_ops_capabilities, get_ocr_providers_readiness
from src.main import app

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "ocr"
PERSIST_FIXTURE = FIXTURE_DIR / "artifact_persist.json"
CAPABILITIES_FIXTURE = FIXTURE_DIR / "capabilities.json"
MIGRATION = Path("alembic/versions/20260717_ocr_artifacts.py")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_ocr_artifact_orm_columns():
    assert OCRArtifact.__tablename__ == "ocr_artifacts"
    assert OCRArtifact.__table__.c.provider.nullable is False
    assert OCRArtifact.__table__.c.page_number.nullable is False
    assert OCRArtifact.__table__.c.content_hash.nullable is False
    assert OCRArtifact.__table__.c.pipeline_version.nullable is False
    index_names = {index.name for index in OCRArtifact.__table__.indexes}
    assert "ix_ocr_artifacts_job_page" in index_names
    assert "ix_ocr_artifacts_draft_page" in index_names


def test_ocr_artifacts_migration_scaffold():
    assert MIGRATION.is_file()
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260717_ocr_artifacts"' in text
    assert 'down_revision: Union[str, Sequence[str], None] = "20260717_inv_tmpl_normalize"' in text
    assert "ocr_artifacts" in text
    assert "canonical" not in text.lower() or "advisory" in text.lower()


def test_hash_ocr_text_is_deterministic():
    digest_a = hash_ocr_text("The  audit evidence is complete.")
    digest_b = hash_ocr_text("the audit evidence is complete.")
    assert digest_a == digest_b
    assert len(digest_a) == 64


def test_build_page_consensus_persist_hook_invoked():
    captured: list[tuple] = []

    def hook(consensus, candidates):
        captured.append((consensus.selected_provider, len(candidates)))

    candidates = [
        OCRPageCandidate(provider="mistral", page_number=1, text="alpha"),
        OCRPageCandidate(provider="azure_di", page_number=1, text="alpha"),
    ]
    result = build_page_consensus(candidates, persist_hook=hook)
    assert result.selected_provider == "mistral"
    assert captured == [("mistral", 2)]


@pytest.mark.asyncio
async def test_persist_page_consensus_writes_canonical_and_advisory():
    fixture = json.loads(PERSIST_FIXTURE.read_text())
    candidates = [OCRPageCandidate(**item) for item in fixture["candidates"]]
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    service = OCRArtifactService(db)
    consensus, artifacts = await service.persist_page_consensus(
        candidates,
        job_ref=fixture["job_ref"],
        draft_ref=fixture["draft_ref"],
        tenant_id=fixture["tenant_id"],
        reference_text=fixture["reference_text"],
    )

    expected = fixture["expected"]
    assert consensus.page_number == expected["page_number"]
    assert consensus.selected_provider == expected["selected_provider"]
    assert len(artifacts) == expected["artifact_count"]
    assert db.add.call_count == expected["artifact_count"]

    tiers = {artifact.provider: artifact.tier for artifact in artifacts}
    assert tiers[expected["canonical_provider"]] == OCRArtifactTier.CANONICAL
    for provider in expected["advisory_providers"]:
        assert tiers[provider] == OCRArtifactTier.ADVISORY

    canonical = next(a for a in artifacts if a.tier == OCRArtifactTier.CANONICAL)
    assert canonical.job_ref == fixture["job_ref"]
    assert canonical.draft_ref == fixture["draft_ref"]
    assert canonical.pipeline_version == DEFAULT_PIPELINE_VERSION
    assert canonical.content_hash == hash_ocr_text(
        next(c.text for c in candidates if c.provider == expected["canonical_provider"])
    )


@pytest.mark.asyncio
async def test_record_dispute_and_ack_do_not_dial_providers():
    db = AsyncMock()
    db.flush = AsyncMock()
    artifact = OCRArtifact(
        id=7,
        provider="mistral",
        page_number=1,
        content_hash="abc123",
        pipeline_version=DEFAULT_PIPELINE_VERSION,
        tier=OCRArtifactTier.CANONICAL,
    )

    service = OCRArtifactService(db)
    service.get_artifact = AsyncMock(return_value=artifact)

    disputed = await service.record_dispute(artifact_id=7, note="Wrong clause mapping", actor="reviewer@example.com")
    assert disputed is not None
    assert disputed.override_status == OCRArtifactOverrideStatus.DISPUTED
    assert disputed.override_note == "Wrong clause mapping"
    assert disputed.overridden_by == "reviewer@example.com"
    assert disputed.overridden_at is not None

    acknowledged = await service.record_ack(artifact_id=7, note="Looks correct", actor="lead@example.com")
    assert acknowledged is not None
    assert acknowledged.override_status == OCRArtifactOverrideStatus.ACKNOWLEDGED
    assert acknowledged.override_note == "Looks correct"


def test_ocr_ops_capabilities_match_fixture():
    fixture = json.loads(CAPABILITIES_FIXTURE.read_text())
    result = get_ocr_ops_capabilities()
    for key, value in fixture["capabilities"].items():
        assert result[key] == value
    assert result["endpoints"] == fixture["endpoints"]


def test_ocr_providers_readiness_includes_capabilities():
    payload = get_ocr_providers_readiness()
    assert payload["capabilities"]["ocr_artifacts_table"] is True
    assert payload["capabilities"]["dispute_ack_stubs"] is True
    assert "e4_non_goal" in payload["capabilities"]


def test_ocr_capabilities_meta_endpoint(client: TestClient):
    response = client.get("/api/v1/health/meta/ocr-capabilities")
    assert response.status_code == 200
    data = response.json()
    assert data["ocr_artifacts_table"] is True
    assert data["page_consensus_persist"] is True
    assert data["provider_dial_on_probes"] is False
    assert data["endpoint"] == "/api/v1/meta/ocr-capabilities"
    assert data["legacy_endpoint"] == "/api/v1/health/meta/ocr-capabilities"

    canonical = client.get("/api/v1/meta/ocr-capabilities")
    assert canonical.status_code == 200
    assert canonical.json()["endpoint"] == "/api/v1/meta/ocr-capabilities"


def test_dispute_stub_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/v1/health/meta/ocr-artifacts/dispute",
        json={"artifact_id": 99, "note": "Needs review", "actor": "ops@example.com"},
    )
    assert response.status_code in {401, 403}


def test_dispute_stub_route_contract(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    from types import SimpleNamespace

    from src.api.dependencies import get_current_user
    from src.main import app

    artifact = OCRArtifact(
        id=99,
        provider="mistral",
        page_number=2,
        content_hash="deadbeef" * 8,
        pipeline_version=DEFAULT_PIPELINE_VERSION,
        tier=OCRArtifactTier.ADVISORY,
        override_status=OCRArtifactOverrideStatus.DISPUTED,
        override_note="Needs review",
        overridden_by="ops@example.com",
    )

    class StubService:
        def __init__(self, db):
            self.db = db
            self.db.commit = AsyncMock()

        async def record_dispute(self, **kwargs):
            return artifact

    monkeypatch.setattr("src.api.routes.ocr_ops.OCRArtifactService", StubService)

    async def _user():
        return SimpleNamespace(id=1, email="ops@example.com", tenant_id=1, is_superuser=True)

    app.dependency_overrides[get_current_user] = _user
    try:
        response = client.post(
            "/api/v1/health/meta/ocr-artifacts/dispute",
            json={"artifact_id": 99, "note": "Needs review", "actor": "ops@example.com"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["stub"] is True
        assert body["provider_dialed"] is False
        assert body["artifact"]["override_status"] == "disputed"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_readyz_includes_ocr_capabilities(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)

    response = client.get("/api/v1/health/readyz")
    assert response.status_code in {200, 503}
    capabilities = response.json().get("checks", {}).get("ocr_providers", {}).get("capabilities", {})
    assert capabilities.get("page_consensus_persist") is True
    assert capabilities.get("dispute_ack_stubs") is True
