"""Integration tests for Portal Near Miss data fidelity and attachment linking.

Covers the world-class data integrity requirements for public portal intake:
- reporter_submission snapshot is preserved (via the immutable audit log, since
  NearMiss has no reporter_submission column like Incident/Complaint/RTA)
- every reporter-submitted field is promoted onto the NearMiss row
- the reporter-submitted event date/time is honoured, not overwritten with
  server ``utcnow``
- ``attachment_ids`` are linked to the created case, failing closed for
  missing/wrong-tenant evidence assets
- an optional ``Idempotency-Key`` / ``idempotency_key`` prevents duplicate
  portal submissions
"""

import uuid

import pytest
from sqlalchemy import select

from src.domain.models.audit_log import AuditLogEntry
from src.domain.models.evidence_asset import EvidenceAsset, EvidenceAssetType, EvidenceSourceModule, EvidenceVisibility
from src.domain.models.near_miss import NearMiss


def _near_miss_payload(**overrides) -> dict:
    payload = {
        "report_type": "near_miss",
        "title": "Near Miss - Test Contract - Loading Bay",
        "description": "Forklift nearly struck a pedestrian near the loading bay.",
        "location": "Loading Bay 3",
        "severity": "high",
        "reporter_name": "Portal Reporter",
        "reporter_email": f"reporter-{uuid.uuid4().hex[:8]}@example.com",
        "reporter_phone": "07123456789",
        "department": "Test Contract",
        "is_anonymous": False,
        "reporter_submission": {
            "contract": "Test Contract",
            "location": "Loading Bay 3",
            "location_coordinates": "51.5074, -0.1278",
            "event_date": "2026-02-10",
            "event_time": "14:30",
            "was_involved": True,
            "reporter_role": "Warehouse Operative",
            "potential_severity": "high",
            "potential_consequences": "Could have caused serious crush injury.",
            "preventive_action_suggested": "Install mirrors at blind junction.",
            "persons_involved": "Jane Smith",
            "witnesses_present": True,
            "witness_names": "John Witness",
            "asset_number": "FLT-042",
            "asset_type": "Forklift",
            "risk_category": "vehicle",
            "is_hipo": True,
        },
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
class TestPortalNearMissFieldPromotion:
    """Every reporter-submitted field must land on the NearMiss row."""

    async def test_all_submitted_fields_are_promoted(self, client, test_session):
        response = await client.post("/api/v1/portal/reports/", json=_near_miss_payload())
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()

        assert near_miss.reporter_role == "Warehouse Operative"
        assert near_miss.reporter_phone == "07123456789"
        assert near_miss.location_coordinates == "51.5074, -0.1278"
        assert near_miss.potential_consequences == "Could have caused serious crush injury."
        assert near_miss.preventive_action_suggested == "Install mirrors at blind junction."
        assert near_miss.persons_involved == "Jane Smith"
        assert near_miss.witnesses_present is True
        assert near_miss.witness_names == "John Witness"
        assert near_miss.asset_number == "FLT-042"
        assert near_miss.asset_type == "Forklift"
        assert near_miss.risk_category == "vehicle"
        assert near_miss.is_hipo is True
        assert near_miss.potential_severity == "high"
        assert near_miss.was_involved is True

    async def test_submitted_event_date_time_is_not_overwritten(self, client, test_session):
        """The client-submitted event date/time must be used, never server utcnow."""
        response = await client.post("/api/v1/portal/reports/", json=_near_miss_payload())
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()

        assert near_miss.event_date.date().isoformat() == "2026-02-10"
        assert near_miss.event_time == "14:30"

    async def test_missing_event_date_falls_back_to_now(self, client, test_session):
        """No client-submitted date/time should still succeed with a server fallback."""
        payload = _near_miss_payload()
        del payload["reporter_submission"]["event_date"]
        del payload["reporter_submission"]["event_time"]

        response = await client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()
        assert near_miss.event_date is not None


@pytest.mark.asyncio
class TestPortalNearMissReporterSubmissionSnapshot:
    """NearMiss has no reporter_submission column; the raw snapshot must still be preserved."""

    async def test_snapshot_persisted_in_audit_log(self, client, test_session):
        payload = _near_miss_payload()
        response = await client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()

        audit_result = await test_session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.entity_type == "near_miss",
                AuditLogEntry.entity_id == str(near_miss.id),
                AuditLogEntry.action == "portal_submit",
            )
        )
        entry = audit_result.scalar_one_or_none()
        assert entry is not None, "Expected an immutable audit snapshot of the raw reporter_submission"
        assert entry.new_values["asset_number"] == "FLT-042"
        assert entry.new_values["potential_consequences"] == "Could have caused serious crush injury."


@pytest.mark.asyncio
class TestPortalNearMissAttachmentFidelity:
    """attachment_ids must be linked to the created case, failing closed on invalid ids."""

    async def _make_asset(self, test_session, *, tenant_id: int) -> EvidenceAsset:
        asset = EvidenceAsset(
            storage_key=f"evidence/pending/{uuid.uuid4().hex}.jpg",
            original_filename="near_miss.jpg",
            content_type="image/jpeg",
            asset_type=EvidenceAssetType.PHOTO,
            source_module=EvidenceSourceModule.NEAR_MISS,
            source_id="0",
            visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
            tenant_id=tenant_id,
        )
        test_session.add(asset)
        await test_session.commit()
        await test_session.refresh(asset)
        return asset

    async def test_valid_attachment_ids_are_linked_to_created_case(self, client, test_session):
        asset = await self._make_asset(test_session, tenant_id=1)

        payload = _near_miss_payload(attachment_ids=[str(asset.id)])
        response = await client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        nm_result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = nm_result.scalar_one()

        await test_session.refresh(asset)
        assert asset.source_module == EvidenceSourceModule.NEAR_MISS
        assert asset.source_id == str(near_miss.id)

    async def test_wrong_tenant_attachment_id_fails_closed(self, client, test_session):
        asset = await self._make_asset(test_session, tenant_id=999)

        payload = _near_miss_payload(attachment_ids=[str(asset.id)])
        response = await client.post("/api/v1/portal/reports/", json=payload)

        assert response.status_code == 422, response.text

        # The case must NOT have been created — fail-closed means no orphaned case.
        nm_result = await test_session.execute(
            select(NearMiss).where(NearMiss.description == payload["description"])
        )
        assert nm_result.scalar_one_or_none() is None

    async def test_missing_attachment_id_fails_closed(self, client, test_session):
        payload = _near_miss_payload(attachment_ids=["999999999"])
        response = await client.post("/api/v1/portal/reports/", json=payload)

        assert response.status_code == 422, response.text
        nm_result = await test_session.execute(
            select(NearMiss).where(NearMiss.description == payload["description"])
        )
        assert nm_result.scalar_one_or_none() is None


@pytest.mark.asyncio
class TestPortalNearMissIdempotency:
    """Optional idempotency key must prevent duplicate portal submissions."""

    async def test_repeated_idempotency_key_returns_same_reference(self, client, test_session):
        key = f"idem-{uuid.uuid4().hex}"
        payload = _near_miss_payload(idempotency_key=key)

        first = await client.post("/api/v1/portal/reports/", json=payload)
        assert first.status_code == 201, first.text
        second = await client.post("/api/v1/portal/reports/", json=payload)
        assert second.status_code == 201, second.text

        assert first.json()["reference_number"] == second.json()["reference_number"]

        count_result = await test_session.execute(
            select(NearMiss).where(NearMiss.reference_number == first.json()["reference_number"])
        )
        assert len(count_result.scalars().all()) == 1

    async def test_idempotency_key_via_header(self, client, test_session):
        key = f"idem-header-{uuid.uuid4().hex}"
        payload = _near_miss_payload()

        first = await client.post(
            "/api/v1/portal/reports/", json=payload, headers={"Idempotency-Key": key}
        )
        assert first.status_code == 201, first.text
        second = await client.post(
            "/api/v1/portal/reports/", json=payload, headers={"Idempotency-Key": key}
        )
        assert second.status_code == 201, second.text
        assert first.json()["reference_number"] == second.json()["reference_number"]

    async def test_different_keys_create_separate_cases(self, client, test_session):
        payload_a = _near_miss_payload(idempotency_key=f"idem-{uuid.uuid4().hex}")
        payload_b = _near_miss_payload(idempotency_key=f"idem-{uuid.uuid4().hex}")

        first = await client.post("/api/v1/portal/reports/", json=payload_a)
        second = await client.post("/api/v1/portal/reports/", json=payload_b)

        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert first.json()["reference_number"] != second.json()["reference_number"]
