"""PX-222 — the campaign reference is stored, not rebuilt in the browser.

The unit tests mock the session, so they can prove the service *asks* for a
sequential reference. Only a real session proves the SQL behind
``ReferenceNumberService`` actually returns one and that the value survives a
round trip through the API.
"""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from src.domain.models.document import Document

UTC = timezone.utc


async def _make_document(test_session, title: str) -> Document:
    document = Document(
        tenant_id=1,
        title=title,
        file_name="lane-s.pdf",
        file_type="pdf",
        file_path="/tmp/lane-s.pdf",
        file_size=1,
        document_type="policy",
        status="draft",
    )
    test_session.add(document)
    await test_session.commit()
    await test_session.refresh(document)
    return document


@pytest.mark.asyncio
async def test_created_campaign_carries_a_stored_sequential_reference(admin_client: AsyncClient, test_session):
    document = await _make_document(test_session, "Campaign reference SSOT")

    response = await admin_client.post(
        "/api/v1/document-campaigns/campaigns",
        json={"document_id": document.id, "title": "Ref A", "audience_type": "all_users"},
    )
    assert response.status_code == 201, response.text
    body = response.json()

    reference = body["reference_number"]
    assert reference is not None
    prefix, year, sequence = reference.split("-")
    assert prefix == "CAM"
    assert year == str(datetime.now(UTC).year)
    assert sequence.isdigit() and len(sequence) == 4

    # The stored value is what every surface reads back — not the surrogate id.
    fetched = await admin_client.get(f"/api/v1/document-campaigns/campaigns/{body['id']}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["reference_number"] == reference


@pytest.mark.asyncio
async def test_consecutive_campaigns_take_consecutive_references(admin_client: AsyncClient, test_session):
    document = await _make_document(test_session, "Campaign reference sequence")

    references = []
    for index in range(2):
        response = await admin_client.post(
            "/api/v1/document-campaigns/campaigns",
            json={"document_id": document.id, "title": f"Seq {index}", "audience_type": "all_users"},
        )
        assert response.status_code == 201, response.text
        references.append(response.json()["reference_number"])

    first, second = (int(ref.split("-")[2]) for ref in references)
    assert second == first + 1
