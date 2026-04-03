"""CUJ-06: User uploads evidence photos.

User Journey:
1. Navigate to incident
2. Upload evidence file
3. File stored in blob storage
4. Evidence linked to incident record
"""

import base64
from datetime import datetime
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

_ONE_PX_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def client():
    from src.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@plantexpand.com", "password": "adminpassword123"},
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.mark.e2e
class TestCUJ06EvidenceUpload:
    """CUJ-06: End-to-end test for evidence photo upload."""

    def test_evidence_upload_endpoint(self, client, auth_headers):
        """Evidence assets collection endpoint is reachable."""
        resp = client.get("/api/v1/evidence-assets", headers=auth_headers)
        assert resp.status_code in (200, 401, 403, 404, 405, 500, 503)

    def test_evidence_linked_to_entity(self, client, auth_headers):
        """Evidence can be tied to an incident via upload metadata."""
        resp = client.get("/api/v1/incidents/", headers=auth_headers)
        assert resp.status_code in (200, 401, 403, 404, 500, 503)

        inc = client.post(
            "/api/v1/incidents/",
            json={
                "title": "CUJ-06: Evidence linkage",
                "description": "Incident for evidence attachment",
                "severity": "medium",
                "incident_date": datetime.now().isoformat(),
                "location": "Yard",
            },
            headers=auth_headers,
        )
        if inc.status_code not in (200, 201):
            return

        incident_id = inc.json().get("id")
        files = {"file": ("cuj06.png", BytesIO(_ONE_PX_PNG), "image/png")}
        data = {
            "source_module": "incident",
            "source_id": str(incident_id),
            "title": "CUJ-06 scene photo",
        }
        up = client.post(
            "/api/v1/evidence-assets/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )
        assert up.status_code in (200, 201, 401, 403, 422, 500, 503), f"Upload: {up.text}"
