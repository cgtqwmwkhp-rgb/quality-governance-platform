"""Integration tests for Portal Near Miss data fidelity and attachment linking.

Covers the world-class data integrity requirements for public portal intake:
- reporter_submission snapshot is preserved (via the immutable audit log, since
  NearMiss has no reporter_submission column like Incident/Complaint/RTA)
- every reporter-submitted field is promoted onto the NearMiss row
- the reporter-submitted event date/time is honoured, not overwritten with
  server ``utcnow`` — asserted against both the key names the portal actually
  sends (``incident_date``/``incident_time``/``preventive_action``, which come
  from the published template) and the NearMiss domain names kept as aliases
- when no usable event date arrives the submission still succeeds, but the
  server-instant substitution is logged rather than applied silently
- ``attachment_ids`` are linked to the created case, failing closed for
  missing/wrong-tenant evidence assets
- an optional ``Idempotency-Key`` / ``idempotency_key`` prevents duplicate
  portal submissions
"""

import logging
import uuid

import pytest
from sqlalchemy import select

from src.domain.models.audit_log import AuditLogEntry
from src.domain.models.evidence_asset import EvidenceAsset, EvidenceAssetType, EvidenceSourceModule, EvidenceVisibility
from src.domain.models.near_miss import NearMiss
from src.domain.models.tenant import Tenant


def _near_miss_payload(**overrides) -> dict:
    """A submission using the NearMiss domain key names.

    Retained because those names stay supported as aliases; it is *not* the shape
    the portal sends. See :func:`_portal_near_miss_payload`.
    """
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


def _portal_near_miss_payload(**overrides) -> dict:
    """A submission using the key names the portal actually sends.

    ``PortalDynamicForm`` passes the reporter's form data through verbatim, and the
    published ``near-miss`` template names its fields ``incident_date``,
    ``incident_time`` and ``preventive_action`` — not the NearMiss domain names.
    ``complaint_date`` rides along because the renderer seeds one generic set of
    date defaults for every report type.
    """
    payload = _near_miss_payload()
    submission = dict(payload["reporter_submission"])
    submission["incident_date"] = submission.pop("event_date")
    submission["incident_time"] = submission.pop("event_time")
    submission["preventive_action"] = submission.pop("preventive_action_suggested")
    submission["complaint_date"] = submission["incident_date"]
    payload["reporter_submission"] = submission
    payload.update(overrides)
    return payload


# Verbatim from the staging ``portal_submit`` audit snapshot for NM-2026-0002,
# the submission that proved the reporter's date, time and preventive action were
# being discarded. Kept literal so it cannot drift away from what the portal sends.
_CAPTURED_STAGING_SUBMISSION = {
    "incident_date": "2026-07-28",
    "incident_time": "21:26",
    "complaint_date": "2026-07-28",
    "person_name": "UX Super",
    "contract": "openreach",
    "location": "Openreach Exchange, Ipswich - Cable chamber 4",
    "description": (
        "Unsecured chamber lid left open at the footway edge while the engineer returned "
        "to the van for cones. A pedestrian stepped around it without seeing the opening."
    ),
    "potential_consequences": (
        "A member of the public could have fallen into an open chamber, with a serious "
        "lower-limb or head injury and a RIDDOR-reportable public safety event."
    ),
    "preventive_action": (
        "Cones and barriers to be positioned before the lid is lifted, never after. "
        "Add to the pre-start briefing checklist."
    ),
}

_SUBMISSION_SHAPES = pytest.mark.parametrize(
    "build_payload",
    [
        pytest.param(_near_miss_payload, id="domain-keys"),
        pytest.param(_portal_near_miss_payload, id="portal-keys"),
    ],
)


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

    @_SUBMISSION_SHAPES
    async def test_submitted_event_date_time_is_not_overwritten(self, client, test_session, build_payload):
        """The client-submitted event date/time must be used, never server utcnow."""
        response = await client.post("/api/v1/portal/reports/", json=build_payload())
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()

        assert near_miss.event_date.date().isoformat() == "2026-02-10"
        assert near_miss.event_time == "14:30"

    @_SUBMISSION_SHAPES
    async def test_submitted_preventive_action_is_promoted(self, client, test_session, build_payload):
        """The suggested control is the point of a near-miss report; it must survive."""
        response = await client.post("/api/v1/portal/reports/", json=build_payload())
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()

        assert near_miss.preventive_action_suggested == "Install mirrors at blind junction."

    async def test_missing_event_date_falls_back_to_now(self, client, test_session, caplog):
        """No client-submitted date/time should still succeed with a server fallback.

        A safety report must never be rejected over a missing timestamp, but the
        substitution has to be observable: a silent fallback is what let a key-name
        mismatch masquerade as working intake.
        """
        payload = _near_miss_payload()
        for key in ("event_date", "event_time", "incident_date", "incident_time"):
            payload["reporter_submission"].pop(key, None)

        with caplog.at_level(logging.WARNING, logger="src.api.routes.employee_portal"):
            response = await client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()
        assert near_miss.event_date is not None
        # No date was submitted, so no time may be invented to accompany the fallback.
        assert near_miss.event_time is None

        fallback_warnings = [
            record.getMessage() for record in caplog.records if "no usable event date" in record.getMessage()
        ]
        assert fallback_warnings, "The server-instant fallback must be logged, not silent"
        assert reference_number in fallback_warnings[0]
        # The keys that did arrive must be named so the mismatch is diagnosable.
        assert "potential_consequences" in fallback_warnings[0]

    async def test_unparseable_domain_key_does_not_beat_a_usable_portal_key(self, client, test_session):
        """A stale/garbage value under one accepted key must not shadow a real one."""
        payload = _portal_near_miss_payload()
        payload["reporter_submission"]["event_date"] = "not-a-date"

        response = await client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()
        assert near_miss.event_date.date().isoformat() == "2026-02-10"
        assert near_miss.event_time == "14:30"

    async def test_over_long_time_value_is_clipped_not_a_lost_report(self, client, test_session):
        """``event_time`` is varchar(10); an over-long value must not abort the insert."""
        payload = _portal_near_miss_payload()
        payload["reporter_submission"]["incident_date"] = "2026-02-10"
        payload["reporter_submission"]["incident_time"] = "14:30:59.123456"

        response = await client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()
        assert len(near_miss.event_time) <= 10
        # Full precision survives on the timestamp column.
        assert near_miss.event_date.hour == 14
        assert near_miss.event_date.minute == 30
        assert near_miss.event_date.second == 59

    async def test_conflicting_event_dates_are_logged_not_silently_resolved(self, client, test_session, caplog):
        """When both accepted shapes carry a different date, the choice must be observable."""
        payload = _near_miss_payload()
        payload["reporter_submission"]["incident_date"] = "2026-03-15"
        payload["reporter_submission"]["incident_time"] = "09:05"

        with caplog.at_level(logging.WARNING, logger="src.api.routes.employee_portal"):
            response = await client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()
        # Documented precedence: the explicit domain key wins, and the date and time
        # come from the same key pair — never spliced across shapes.
        assert near_miss.event_date.date().isoformat() == "2026-02-10"
        assert near_miss.event_time == "14:30"

        conflict_warnings = [
            record.getMessage() for record in caplog.records if "conflicting event dates" in record.getMessage()
        ]
        assert conflict_warnings, "A conflict between accepted date keys must be logged"
        assert reference_number in conflict_warnings[0]


@pytest.mark.asyncio
class TestPortalNearMissCapturedStagingSubmission:
    """The exact payload staging received, asserting the data loss cannot recur.

    Reproduced from the immutable ``portal_submit`` audit snapshot of NM-2026-0002,
    whose row landed with ``event_time`` NULL, ``preventive_action_suggested`` NULL
    and ``event_date`` equal to the submission instant.
    """

    def _payload(self) -> dict:
        return {
            "report_type": "near_miss",
            "title": "Near Miss Report - openreach",
            "description": _CAPTURED_STAGING_SUBMISSION["description"],
            "location": _CAPTURED_STAGING_SUBMISSION["location"],
            "severity": "medium",
            "reporter_name": "UX Super",
            "reporter_email": f"reporter-{uuid.uuid4().hex[:8]}@example.com",
            "department": "openreach",
            "is_anonymous": False,
            "reporter_submission": dict(_CAPTURED_STAGING_SUBMISSION),
        }

    async def test_entered_date_time_and_preventive_action_all_survive(self, client, test_session):
        response = await client.post("/api/v1/portal/reports/", json=self._payload())
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()

        assert near_miss.event_date.date().isoformat() == "2026-07-28"
        assert near_miss.event_date.hour == 21
        assert near_miss.event_date.minute == 26
        assert near_miss.event_time == "21:26"
        assert near_miss.preventive_action_suggested == _CAPTURED_STAGING_SUBMISSION["preventive_action"]
        assert near_miss.potential_consequences == _CAPTURED_STAGING_SUBMISSION["potential_consequences"]

    async def test_event_date_is_not_the_submission_instant(self, client, test_session):
        """The precise failure mode observed on staging: created_at written as event_date."""
        response = await client.post("/api/v1/portal/reports/", json=self._payload())
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()

        drift = abs((near_miss.event_date - near_miss.created_at).total_seconds())
        assert drift > 5, "event_date tracked created_at — the reporter's entry was overwritten"

    async def test_stray_complaint_date_is_ignored(self, client, test_session):
        """The renderer's generic ``complaint_date`` seed must not become the event date."""
        payload = self._payload()
        payload["reporter_submission"]["complaint_date"] = "2020-01-01"

        response = await client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        result = await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one()
        assert near_miss.event_date.date().isoformat() == "2026-07-28"


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

    async def _ensure_tenant(self, test_session, *, tenant_id: int) -> None:
        existing = await test_session.get(Tenant, tenant_id)
        if existing is not None:
            return
        test_session.add(
            Tenant(
                id=tenant_id,
                name=f"CI Tenant {tenant_id}",
                slug=f"ci-tenant-{tenant_id}",
                admin_email=f"admin-{tenant_id}@example.com",
                is_active=True,
            )
        )
        await test_session.flush()

    async def _make_asset(self, test_session, *, tenant_id: int) -> EvidenceAsset:
        await self._ensure_tenant(test_session, tenant_id=tenant_id)
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

        unique_description = f"Wrong-tenant attachment fail-closed {uuid.uuid4().hex}"
        payload = _near_miss_payload(
            attachment_ids=[str(asset.id)],
            description=unique_description,
        )
        response = await client.post("/api/v1/portal/reports/", json=payload)

        assert response.status_code == 422, response.text

        # The case must NOT have been created — fail-closed means no orphaned case.
        nm_result = await test_session.execute(select(NearMiss).where(NearMiss.description == unique_description))
        assert nm_result.scalars().first() is None

    async def test_missing_attachment_id_fails_closed(self, client, test_session):
        unique_description = f"Missing attachment fail-closed {uuid.uuid4().hex}"
        payload = _near_miss_payload(
            attachment_ids=["999999999"],
            description=unique_description,
        )
        response = await client.post("/api/v1/portal/reports/", json=payload)

        assert response.status_code == 422, response.text
        nm_result = await test_session.execute(select(NearMiss).where(NearMiss.description == unique_description))
        assert nm_result.scalars().first() is None


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

        first = await client.post("/api/v1/portal/reports/", json=payload, headers={"Idempotency-Key": key})
        assert first.status_code == 201, first.text
        second = await client.post("/api/v1/portal/reports/", json=payload, headers={"Idempotency-Key": key})
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
