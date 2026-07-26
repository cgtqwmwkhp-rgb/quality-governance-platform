"""Integration tests for portal evidence upload and linking (PX-327).

The defect these cover: the portal accepted photos and files, listed them in the
UI, then submitted a JSON body that omitted them entirely. The record was stored
with no attachments and the reporter was told the submission succeeded.

So the load-bearing assertion here is end-to-end: a file uploaded through the
portal must still be attached to the case that the portal then creates. The rest
guard the ways that path can fail dishonestly — rejected uploads that look
accepted, handles replayed onto a second case, and evidence lifted off a record
that already owns it.
"""

import uuid

import pytest
from sqlalchemy import select

from src.domain.models.evidence_asset import (
    EvidenceAsset,
    EvidenceAssetType,
    EvidenceRetentionPolicy,
    EvidenceSourceModule,
    EvidenceVisibility,
)
from src.domain.models.near_miss import NearMiss
from src.domain.models.tenant import Tenant
from src.infrastructure.storage import StorageDependencyError

PORTAL_TENANT_ID = 1
UPLOAD_URL = "/api/v1/portal/reports/attachments"
SUBMIT_URL = "/api/v1/portal/reports/"

# Stated here rather than imported, so these assert the agreed contract instead
# of whatever the implementation happens to define. The size ceiling must match
# MAX_UPLOAD_BYTES in frontend/src/components/DynamicForm/DynamicFormRenderer.tsx,
# or the portal will accept a file in the browser that the API then refuses.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PENDING_SOURCE_ID = "0"

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"portal evidence payload" * 8


class _FakeStorage:
    """In-memory stand-in so tests never touch Azure or the local disk."""

    def __init__(self):
        self.blobs: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def upload(self, storage_key, content, content_type, metadata=None):
        self.blobs[storage_key] = content
        return storage_key

    async def delete(self, storage_key):
        self.deleted.append(storage_key)
        self.blobs.pop(storage_key, None)
        return True


class _BrokenStorage:
    """Storage that is reachable-but-failing, as during an Azure outage."""

    async def upload(self, storage_key, content, content_type, metadata=None):
        raise StorageDependencyError("blob storage unavailable")

    async def delete(self, storage_key):
        return True


@pytest.fixture
def fake_storage(monkeypatch):
    storage = _FakeStorage()
    monkeypatch.setattr("src.infrastructure.storage.storage_service", lambda: storage)
    return storage


@pytest.fixture
async def portal_tenant(test_session):
    existing = await test_session.get(Tenant, PORTAL_TENANT_ID)
    if existing is None:
        test_session.add(
            Tenant(
                id=PORTAL_TENANT_ID,
                name="CI Portal Tenant",
                slug="ci-portal-tenant",
                admin_email="admin@example.com",
                is_active=True,
            )
        )
        await test_session.commit()
    return PORTAL_TENANT_ID


def _near_miss_payload(**overrides) -> dict:
    payload = {
        "report_type": "near_miss",
        "title": "Near Miss - Loading Bay Evidence",
        "description": "Forklift nearly struck a pedestrian near the loading bay.",
        "location": "Loading Bay 3",
        "severity": "high",
        "reporter_name": "Portal Reporter",
        "reporter_email": f"reporter-{uuid.uuid4().hex[:8]}@example.com",
        "is_anonymous": False,
        "reporter_submission": {"contract": "Test Contract"},
    }
    payload.update(overrides)
    return payload


async def _upload(client, *, content=JPEG_BYTES, filename="scene.jpg", content_type="image/jpeg"):
    return await client.post(
        UPLOAD_URL,
        files={"file": (filename, content, content_type)},
        data={"report_type": "near_miss"},
    )


@pytest.mark.asyncio
class TestPortalAttachmentUploadAndLink:
    """A file attached in the portal must survive all the way onto the case."""

    async def test_uploaded_file_is_stored_and_linked_to_the_created_case(
        self, client, test_session, fake_storage, portal_tenant
    ):
        upload = await _upload(client)
        assert upload.status_code == 201, upload.text
        receipt = upload.json()

        # The bytes actually reached storage, rather than being counted as
        # attached on the strength of a filename alone.
        assert len(fake_storage.blobs) == 1
        assert next(iter(fake_storage.blobs.values())) == JPEG_BYTES
        assert receipt["size_bytes"] == len(JPEG_BYTES)
        assert receipt["filename"] == "scene.jpg"

        payload = _near_miss_payload(attachment_ids=[receipt["attachment_id"]])
        response = await client.post(SUBMIT_URL, json=payload)
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        near_miss = (
            await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        ).scalar_one()

        asset_id = int(receipt["attachment_id"].split(".")[0])
        asset = await test_session.get(EvidenceAsset, asset_id)
        await test_session.refresh(asset)

        assert asset.source_module == EvidenceSourceModule.NEAR_MISS
        assert asset.source_id == str(near_miss.id)
        assert asset.content_type == "image/jpeg"
        assert asset.file_size_bytes == len(JPEG_BYTES)
        assert asset.asset_type == EvidenceAssetType.PHOTO

    async def test_pending_upload_is_quarantined_until_a_case_claims_it(
        self, client, test_session, fake_storage, portal_tenant
    ):
        upload = await _upload(client)
        assert upload.status_code == 201, upload.text
        asset_id = int(upload.json()["attachment_id"].split(".")[0])

        asset = await test_session.get(EvidenceAsset, asset_id)
        assert asset.source_id == PENDING_SOURCE_ID
        assert asset.tenant_id == PORTAL_TENANT_ID
        # Un-triaged content from an anonymous reporter must not default into a
        # customer pack, and must expire rather than linger if never claimed.
        assert asset.visibility == EvidenceVisibility.INTERNAL_ONLY
        assert asset.retention_policy == EvidenceRetentionPolicy.TEMPORARY
        assert asset.retention_expires_at is not None

    async def test_linking_promotes_the_asset_out_of_temporary_retention(
        self, client, test_session, fake_storage, portal_tenant
    ):
        upload = await _upload(client)
        handle = upload.json()["attachment_id"]

        response = await client.post(SUBMIT_URL, json=_near_miss_payload(attachment_ids=[handle]))
        assert response.status_code == 201, response.text

        asset = await test_session.get(EvidenceAsset, int(handle.split(".")[0]))
        await test_session.refresh(asset)
        assert asset.retention_policy == EvidenceRetentionPolicy.STANDARD
        assert asset.retention_expires_at is None

    async def test_multiple_files_are_all_linked(self, client, test_session, fake_storage, portal_tenant):
        handles = []
        for index in range(3):
            upload = await _upload(client, filename=f"evidence-{index}.jpg")
            assert upload.status_code == 201, upload.text
            handles.append(upload.json()["attachment_id"])

        response = await client.post(SUBMIT_URL, json=_near_miss_payload(attachment_ids=handles))
        assert response.status_code == 201, response.text
        reference_number = response.json()["reference_number"]

        near_miss = (
            await test_session.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        ).scalar_one()

        linked = (
            (
                await test_session.execute(
                    select(EvidenceAsset).where(
                        EvidenceAsset.source_module == EvidenceSourceModule.NEAR_MISS,
                        EvidenceAsset.source_id == str(near_miss.id),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(linked) == 3


@pytest.mark.asyncio
class TestPortalAttachmentUploadRejections:
    """Every rejection must be loud. A refused file must never look accepted."""

    async def test_file_over_the_size_limit_is_rejected(self, client, fake_storage, portal_tenant):
        oversized = b"\xff\xd8\xff\xe0" + b"x" * MAX_UPLOAD_BYTES

        response = await _upload(client, content=oversized, filename="huge.jpg")

        assert response.status_code == 413, response.text
        assert fake_storage.blobs == {}

    async def test_disallowed_content_type_is_rejected(self, client, fake_storage, portal_tenant):
        response = await _upload(
            client,
            content=b"MZ\x90\x00executable",
            filename="payload.exe",
            content_type="application/x-msdownload",
        )

        assert response.status_code == 422, response.text
        assert fake_storage.blobs == {}

        # The portal renders this straight to the reporter, so the rejection has
        # to say what was wrong rather than leaving them at "please try again".
        message = response.json()["error"]["message"]
        assert "application/x-msdownload" in message
        assert response.json()["error"]["details"]["allowed_types"]

    async def test_video_is_rejected_even_though_staff_upload_allows_it(self, client, fake_storage, portal_tenant):
        response = await _upload(
            client, content=b"\x00\x00\x00 ftypmp42", filename="clip.mp4", content_type="video/mp4"
        )

        assert response.status_code == 422, response.text

    async def test_empty_file_is_rejected(self, client, fake_storage, portal_tenant):
        response = await _upload(client, content=b"", filename="empty.jpg")

        assert response.status_code == 422, response.text
        assert fake_storage.blobs == {}

    async def test_unknown_report_type_is_rejected(self, client, fake_storage, portal_tenant):
        response = await client.post(
            UPLOAD_URL,
            files={"file": ("scene.jpg", JPEG_BYTES, "image/jpeg")},
            data={"report_type": "not_a_report_type"},
        )

        assert response.status_code == 422, response.text
        assert fake_storage.blobs == {}

    async def test_storage_outage_fails_the_upload_rather_than_reporting_success(
        self, client, test_session, monkeypatch, portal_tenant
    ):
        monkeypatch.setattr("src.infrastructure.storage.storage_service", lambda: _BrokenStorage())

        before = len((await test_session.execute(select(EvidenceAsset))).scalars().all())
        response = await _upload(client)

        assert response.status_code == 503, response.text
        after = len((await test_session.execute(select(EvidenceAsset))).scalars().all())
        assert after == before, "A failed upload must not leave an asset row behind"


@pytest.mark.asyncio
class TestPortalAttachmentLinkingIsFailClosed:
    """Handles are single-use, tenant-bound, and cannot claim someone's evidence."""

    async def _linked_asset(self, test_session, *, source_id: str) -> EvidenceAsset:
        asset = EvidenceAsset(
            tenant_id=PORTAL_TENANT_ID,
            storage_key=f"evidence/near_miss/{uuid.uuid4().hex}.jpg",
            original_filename="already_on_a_case.jpg",
            content_type="image/jpeg",
            asset_type=EvidenceAssetType.PHOTO,
            source_module=EvidenceSourceModule.NEAR_MISS,
            source_id=source_id,
            visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
        )
        test_session.add(asset)
        await test_session.commit()
        await test_session.refresh(asset)
        return asset

    async def test_evidence_already_attached_to_a_record_cannot_be_relinked(
        self, client, test_session, fake_storage, portal_tenant
    ):
        """A public caller must not be able to lift evidence off an existing case."""
        victim = await self._linked_asset(test_session, source_id="4242")

        description = f"Relink attempt {uuid.uuid4().hex}"
        response = await client.post(
            SUBMIT_URL,
            json=_near_miss_payload(attachment_ids=[str(victim.id)], description=description),
        )

        assert response.status_code == 422, response.text
        await test_session.refresh(victim)
        assert victim.source_id == "4242", "Evidence was moved off the record that owned it"

        orphaned = await test_session.execute(select(NearMiss).where(NearMiss.description == description))
        assert orphaned.scalars().first() is None

    async def test_handle_cannot_be_replayed_onto_a_second_case(
        self, client, test_session, fake_storage, portal_tenant
    ):
        handle = (await _upload(client)).json()["attachment_id"]

        first = await client.post(SUBMIT_URL, json=_near_miss_payload(attachment_ids=[handle]))
        assert first.status_code == 201, first.text

        description = f"Replay attempt {uuid.uuid4().hex}"
        second = await client.post(
            SUBMIT_URL,
            json=_near_miss_payload(attachment_ids=[handle], description=description),
        )

        assert second.status_code == 422, second.text
        replayed = await test_session.execute(select(NearMiss).where(NearMiss.description == description))
        assert replayed.scalars().first() is None

    async def test_guessing_the_numeric_id_without_the_token_is_rejected(
        self, client, test_session, fake_storage, portal_tenant
    ):
        """Asset ids are sequential, so the id alone must not claim an upload."""
        handle = (await _upload(client)).json()["attachment_id"]
        asset_id = handle.split(".")[0]

        description = f"Token guess {uuid.uuid4().hex}"
        response = await client.post(
            SUBMIT_URL,
            json=_near_miss_payload(attachment_ids=[asset_id], description=description),
        )

        assert response.status_code == 422, response.text
        asset = await test_session.get(EvidenceAsset, int(asset_id))
        await test_session.refresh(asset)
        assert asset.source_id == PENDING_SOURCE_ID

    async def test_wrong_token_is_rejected(self, client, test_session, fake_storage, portal_tenant):
        handle = (await _upload(client)).json()["attachment_id"]
        asset_id = handle.split(".")[0]

        response = await client.post(
            SUBMIT_URL,
            json=_near_miss_payload(attachment_ids=[f"{asset_id}.not-the-real-token"]),
        )

        assert response.status_code == 422, response.text
