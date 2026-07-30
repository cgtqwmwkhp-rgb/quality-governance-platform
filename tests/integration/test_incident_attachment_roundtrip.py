"""Incident evidence upload → re-read probe (PX-327 / w4-px327-probe).

``tests/contract/test_write_contract_guards.py`` documents a deliberate blind
spot: ``attachments`` is on neither the incident request nor response schema,
so schema-driven round-trip guards cannot see the defect class that PX-327
exposed (accepted attachment, nothing readable back on the owning record).

Portal intake is already covered by ``test_portal_attachment_upload.py``.
This module covers the authenticated staff path that IncidentDetail uses:
``POST /api/v1/evidence-assets/upload`` with ``source_module=incident``, then
``GET /api/v1/evidence-assets/?source_module=incident&source_id=…``.

The load-bearing assertion is that a 201 upload is still listed against the
incident that owns it. A green write-contract suite alone is not evidence of
that property.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from tests.integration.conftest import _ADMIN_PERMS, _generate_test_jwt

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"incident evidence payload" * 8
UPLOAD_URL = "/api/v1/evidence-assets/upload"
LIST_URL = "/api/v1/evidence-assets/"


class _FakeStorage:
    """In-memory stand-in so the probe never touches Azure or local disk."""

    def __init__(self):
        self.blobs: dict[str, bytes] = {}

    async def upload(self, storage_key, content, content_type, metadata=None):
        self.blobs[storage_key] = content
        return storage_key

    async def delete(self, storage_key):
        self.blobs.pop(storage_key, None)
        return True


@pytest.fixture
def fake_storage(monkeypatch):
    storage = _FakeStorage()
    monkeypatch.setattr("src.infrastructure.storage.storage_service", lambda: storage)
    return storage


@pytest.fixture
def evidence_auth_headers() -> dict[str, str]:
    """Admin JWT plus ``evidence:create`` (not in the default admin persona)."""
    token = _generate_test_jwt(permissions=f"{_ADMIN_PERMS},evidence:create")
    return {"Authorization": f"Bearer {token}"}


async def _create_incident(client: AsyncClient, headers: dict[str, str]) -> int:
    response = await client.post(
        "/api/v1/incidents/",
        json={
            "title": "PX-327 attachment round-trip probe",
            "description": "Owning record for evidence upload → list re-read.",
            "incident_type": "injury",
            "severity": "low",
            "status": "reported",
            "incident_date": datetime.now(timezone.utc).isoformat(),
            "location": "Yard",
            "department": "Operations",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


@pytest.mark.asyncio
async def test_incident_evidence_upload_is_re_readable_on_owning_record(
    client: AsyncClient,
    evidence_auth_headers,
    fake_storage,
):
    """Upload accepted for an incident must appear when listing that incident's evidence."""
    incident_id = await _create_incident(client, evidence_auth_headers)

    # Incident schemas deliberately omit attachments — GET must not be treated
    # as the attachment read path (that is the #1387 blind spot).
    detail = await client.get(f"/api/v1/incidents/{incident_id}", headers=evidence_auth_headers)
    assert detail.status_code == 200, detail.text
    assert "attachments" not in detail.json()

    upload = await client.post(
        UPLOAD_URL,
        files={"file": ("scene.jpg", JPEG_BYTES, "image/jpeg")},
        data={
            "source_module": "incident",
            "source_id": str(incident_id),
            "title": "Scene photo",
        },
        headers=evidence_auth_headers,
    )
    assert upload.status_code == 201, upload.text
    receipt = upload.json()
    asset_id = receipt["id"]
    assert receipt["original_filename"] == "scene.jpg"
    assert receipt["file_size_bytes"] == len(JPEG_BYTES)
    assert len(fake_storage.blobs) == 1
    assert next(iter(fake_storage.blobs.values())) == JPEG_BYTES

    listed = await client.get(
        LIST_URL,
        params={
            "source_module": "incident",
            "source_id": incident_id,
            "page_size": 50,
        },
        headers=evidence_auth_headers,
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    items = body["items"]
    assert body["total"] >= 1
    match = next((item for item in items if item["id"] == asset_id), None)
    assert match is not None, (
        f"Uploaded evidence asset {asset_id} was accepted (201) but not returned when "
        f"listing evidence for incident {incident_id}. items={[i.get('id') for i in items]}"
    )
    assert match["source_module"] == "incident"
    assert str(match["source_id"]) == str(incident_id)
    assert match["original_filename"] == "scene.jpg"
    assert match["file_size_bytes"] == len(JPEG_BYTES)

    fetched = await client.get(f"/api/v1/evidence-assets/{asset_id}", headers=evidence_auth_headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == asset_id
    assert str(fetched.json()["source_id"]) == str(incident_id)


@pytest.mark.asyncio
async def test_incident_evidence_list_does_not_leak_other_incidents(
    client: AsyncClient,
    evidence_auth_headers,
    fake_storage,
):
    """Filter by source_id must not surface evidence attached to a different incident."""
    first_id = await _create_incident(client, evidence_auth_headers)
    second_id = await _create_incident(client, evidence_auth_headers)

    upload = await client.post(
        UPLOAD_URL,
        files={"file": ("only-on-first.jpg", JPEG_BYTES, "image/jpeg")},
        data={
            "source_module": "incident",
            "source_id": str(first_id),
            "title": "First only",
        },
        headers=evidence_auth_headers,
    )
    assert upload.status_code == 201, upload.text
    asset_id = upload.json()["id"]

    listed = await client.get(
        LIST_URL,
        params={"source_module": "incident", "source_id": second_id},
        headers=evidence_auth_headers,
    )
    assert listed.status_code == 200, listed.text
    ids = [item["id"] for item in listed.json()["items"]]
    assert asset_id not in ids
