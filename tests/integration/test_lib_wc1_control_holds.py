"""WC-1 — legal holds freeze the document lifecycle; control folds onto the Register.

Two things are proved here against a real database rather than a scripted session,
because both are the kind of control that passes a mocked test while being wired
to nothing:

1. **A hold refuses the write.** ``matter_legal_holds`` existed and was enforced
   nowhere: a document could be revised, approved, published, obsoleted and
   hard-deleted by the disposal queue while a matter it belongs to was under
   hold. Each refusal is asserted on the HTTP surface a user reaches, with the
   released-hold case asserted beside it so "refuses everything" cannot pass.

2. **One Register (L-01d).** A control record is anchored to a Register row, an
   anchor cannot be taken twice, and a library publish moves the anchored control
   record in the same transaction — so Document Control can no longer show
   ``draft`` for a document the Register has published.

Every seeded document is authored by a third user, distinct from both clients, so
the separation-of-duties refusal added to publish does not fire incidentally and
mask a hold assertion. ``admin_client`` is user 1 and ``superuser_client`` is
user 2; hold administration needs ``admin:manage``, which only the latter has.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.document import Document, DocumentVersion, FileType
from src.domain.models.document_control import ControlledDocument
from src.domain.models.enums import DocumentStatus
from src.infrastructure.database import async_session_maker

TENANT = 1
_AUTHOR_EMAIL = "wc1-author@test.example.com"

#: Sentinel for "the third-party author", resolved to a real user id per call.
#: ``documents.created_by_id`` is a real foreign key, so the author has to exist:
#: PostgreSQL (CI) enforces it even though SQLite (local default) does not.
AUTHOR = object()


async def _author_id() -> int:
    """The id of a user who is neither ``admin_client`` (1) nor ``superuser_client`` (2)."""
    from src.core.security import get_password_hash
    from src.domain.models.user import User
    from tests.factories import UserFactory

    async with async_session_maker() as session:
        existing = await session.scalar(select(User.id).where(User.email == _AUTHOR_EMAIL))
        if existing is not None:
            return int(existing)
        author = UserFactory.build(
            email=_AUTHOR_EMAIL,
            hashed_password=get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
            tenant_id=TENANT,
        )
        author.id = None
        session.add(author)
        await session.commit()
        return int(author.id)


async def _seed_document(
    *,
    status: DocumentStatus = DocumentStatus.DRAFT,
    created_by_id: object = AUTHOR,
    matter_reference: str | None = None,
    retention_until=None,
    tenant_id: int = TENANT,
) -> int:
    """Insert one active Register row and return its id."""
    author_id = await _author_id() if created_by_id is AUTHOR else created_by_id
    document = Document(
        tenant_id=tenant_id,
        reference_number=f"DOC-{uuid.uuid4().hex[:14]}",
        title=f"WC-1 hold probe {uuid.uuid4().hex[:8]}",
        description="Seeded for the WC-1 legal-hold enforcement tests.",
        file_name="wc1-probe.pdf",
        file_type=FileType.PDF,
        file_size=2048,
        file_path=f"seed/wc1/{uuid.uuid4().hex}.pdf",
        status=status,
        version="1.0",
        is_active=True,
        created_by_id=author_id,
        legal_matter_reference=matter_reference,
        retention_until=retention_until,
    )
    async with async_session_maker() as session:
        session.add(document)
        await session.commit()
        return int(document.id)


async def _seed_draft_version(document_id: int) -> int:
    async with async_session_maker() as session:
        version = DocumentVersion(
            tenant_id=TENANT,
            document_id=document_id,
            version_number="1.0",
            change_notes="Seeded draft tip",
            change_type="new",
            status="draft",
            is_immutable=False,
            file_name="wc1-probe.pdf",
            file_path=f"seed/wc1/{uuid.uuid4().hex}.pdf",
            file_size=2048,
            created_by_id=await _author_id(),
        )
        session.add(version)
        await session.commit()
        return int(version.id)


async def _seed_controlled(*, library_document_id: int | None, status: str = "draft") -> int:
    async with async_session_maker() as session:
        controlled = ControlledDocument(
            tenant_id=TENANT,
            document_number=f"WC1-{uuid.uuid4().hex[:8].upper()}",
            title=f"WC-1 control shell {uuid.uuid4().hex[:6]}",
            document_type="policy",
            category="policies",
            current_version="1.0",
            major_version=1,
            minor_version=0,
            status=status,
            is_current=True,
            library_document_id=library_document_id,
        )
        session.add(controlled)
        await session.commit()
        return int(controlled.id)


async def _controlled_row(controlled_id: int) -> ControlledDocument:
    async with async_session_maker() as session:
        row = await session.scalar(select(ControlledDocument).where(ControlledDocument.id == controlled_id))
        assert row is not None
        return row


async def _file_under_matter(client: AsyncClient, document_id: int, matter: str | None) -> dict:
    res = await client.put(
        f"/api/v1/legal-holds/documents/{document_id}",
        json={"matter_reference": matter},
    )
    assert res.status_code == 200, f"hold scope write -> {res.status_code} {res.text}"
    return res.json()


async def _issue_hold(client: AsyncClient, matter: str) -> int:
    res = await client.post("/api/v1/legal-holds", json={"matter_reference": matter})
    assert res.status_code == 201, f"hold create -> {res.status_code} {res.text}"
    return int(res.json()["id"])


async def _revise(client: AsyncClient, document_id: int) -> "object":
    return await client.post(
        f"/api/v1/documents/{document_id}/versions",
        data={"change_notes": "WC-1 revision attempt", "change_type": "revision"},
    )


def _assert_hold_refusal(response, *, matter: str) -> None:
    assert response.status_code == 409, f"expected a hold refusal, got {response.status_code} {response.text}"
    body = response.json()
    payload = body.get("error", body)
    assert payload.get("code") == "LEGAL_HOLD_ACTIVE", body
    assert matter in response.text


# ---------------------------------------------------------------------------
# 1. A hold refuses the write
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_is_refused_while_the_matter_is_held(
    admin_client: AsyncClient,
    superuser_client: AsyncClient,
) -> None:
    matter = f"MATTER-{uuid.uuid4().hex[:8]}"
    document_id = await _seed_document()
    await _file_under_matter(superuser_client, document_id, matter)

    # Filed under a matter with no hold: the write is untouched. Without this the
    # refusal below could be any unrelated 409 on the same endpoint.
    allowed = await _revise(admin_client, document_id)
    assert allowed.status_code == 201, f"revise before the hold -> {allowed.status_code} {allowed.text}"

    await _issue_hold(superuser_client, matter)

    refused = await _revise(admin_client, document_id)
    _assert_hold_refusal(refused, matter=matter)


@pytest.mark.asyncio
async def test_released_hold_lets_the_lifecycle_move_again(
    admin_client: AsyncClient,
    superuser_client: AsyncClient,
) -> None:
    """A released hold must stop refusing, or the control is a one-way door."""
    matter = f"MATTER-{uuid.uuid4().hex[:8]}"
    document_id = await _seed_document()
    await _file_under_matter(superuser_client, document_id, matter)
    hold_id = await _issue_hold(superuser_client, matter)

    _assert_hold_refusal(await _revise(admin_client, document_id), matter=matter)

    release = await superuser_client.post(f"/api/v1/legal-holds/{hold_id}/release")
    assert release.status_code == 200, release.text

    after = await _revise(admin_client, document_id)
    assert after.status_code == 201, f"revise after release -> {after.status_code} {after.text}"


@pytest.mark.asyncio
async def test_a_document_outside_the_held_matter_is_untouched(
    admin_client: AsyncClient,
    superuser_client: AsyncClient,
) -> None:
    """Scope matters: a hold freezes its own matter, not the whole library."""
    held_matter = f"MATTER-{uuid.uuid4().hex[:8]}"
    other_matter = f"MATTER-{uuid.uuid4().hex[:8]}"
    held_id = await _seed_document()
    other_id = await _seed_document()
    unfiled_id = await _seed_document()

    await _file_under_matter(superuser_client, held_id, held_matter)
    await _file_under_matter(superuser_client, other_id, other_matter)
    await _issue_hold(superuser_client, held_matter)

    _assert_hold_refusal(await _revise(admin_client, held_id), matter=held_matter)

    for allowed_id, label in ((other_id, "different matter"), (unfiled_id, "no matter")):
        response = await _revise(admin_client, allowed_id)
        assert response.status_code == 201, f"{label} was refused: {response.status_code} {response.text}"


@pytest.mark.asyncio
async def test_an_empty_hold_freezes_nothing(
    admin_client: AsyncClient,
    superuser_client: AsyncClient,
) -> None:
    """A hold whose matter covers no document must not freeze the library.

    This is the state a hold is issued in — the instruction arrives before anyone
    has filed records against it — so the fail-closed direction must not be read
    as "any active hold refuses everything".
    """
    await _issue_hold(superuser_client, f"MATTER-{uuid.uuid4().hex[:8]}")

    document_id = await _seed_document()
    response = await _revise(admin_client, document_id)
    assert response.status_code == 201, f"an unrelated hold refused a revise: {response.text}"


@pytest.mark.asyncio
async def test_publish_and_approve_are_refused_while_held(
    admin_client: AsyncClient,
    superuser_client: AsyncClient,
) -> None:
    matter = f"MATTER-{uuid.uuid4().hex[:8]}"

    publish_id = await _seed_document()
    await _seed_draft_version(publish_id)
    approve_id = await _seed_document(status=DocumentStatus.UNDER_REVIEW)
    await _seed_draft_version(approve_id)
    for document_id in (publish_id, approve_id):
        await _file_under_matter(superuser_client, document_id, matter)
    await _issue_hold(superuser_client, matter)

    _assert_hold_refusal(await admin_client.post(f"/api/v1/documents/{publish_id}/publish"), matter=matter)
    _assert_hold_refusal(await admin_client.post(f"/api/v1/documents/{approve_id}/approve"), matter=matter)


@pytest.mark.asyncio
async def test_metadata_edit_is_refused_while_held(
    admin_client: AsyncClient,
    superuser_client: AsyncClient,
) -> None:
    matter = f"MATTER-{uuid.uuid4().hex[:8]}"
    document_id = await _seed_document()
    await _file_under_matter(superuser_client, document_id, matter)
    await _issue_hold(superuser_client, matter)

    refused = await admin_client.patch(
        f"/api/v1/documents/{document_id}",
        json={"title": "Retitled while under hold"},
    )
    _assert_hold_refusal(refused, matter=matter)

    async with async_session_maker() as session:
        row = await session.scalar(select(Document).where(Document.id == document_id))
        assert row is not None
        assert row.title != "Retitled while under hold", "the refused edit was applied anyway"


@pytest.mark.asyncio
async def test_disposal_never_lists_or_deletes_a_held_document(
    admin_client: AsyncClient,
    superuser_client: AsyncClient,
) -> None:
    """The hold predicate is inside the disposal statement, not beside it.

    Disposal hard-deletes the row and its blob, so this is the path where a
    missed hold is unrecoverable rather than merely wrong.
    """
    due = datetime.now(timezone.utc) - timedelta(days=1)
    matter = f"MATTER-{uuid.uuid4().hex[:8]}"
    held_id = await _seed_document(status=DocumentStatus.OBSOLETE, retention_until=due)
    free_id = await _seed_document(status=DocumentStatus.OBSOLETE, retention_until=due)
    await _file_under_matter(superuser_client, held_id, matter)
    await _issue_hold(superuser_client, matter)

    preview = await superuser_client.get("/api/v1/documents/admin/disposal?limit=100")
    assert preview.status_code == 200, preview.text
    candidate_ids = {int(item["document_id"]) for item in preview.json()["items"]}
    assert held_id not in candidate_ids, "a held document was offered for disposal"
    assert free_id in candidate_ids, "the eligible control document was not offered"

    # The HTTP execute route is behind the LIBRARY_DISPOSAL_EXECUTE kill switch,
    # which is off in this harness, so the delete itself is driven at the service
    # boundary. Both ids are named explicitly: the eligible one proves the sweep
    # really does hard-delete, so the held one surviving is the hold working and
    # not the sweep being inert.
    from src.domain.services.document_library_disposal_service import execute_disposal

    async with async_session_maker() as session:
        # ``as_of`` is derived from a round-tripped value so its tz-awareness matches
        # whatever the backend under test returns: this suite runs on SQLite locally
        # (naive) and PostgreSQL in CI (aware), and the eligibility comparison is
        # done in Python.
        stored_due = await session.scalar(select(Document.retention_until).where(Document.id == free_id))
        assert stored_due is not None
        disposed = await execute_disposal(
            session,
            tenant_id=TENANT,
            document_ids=[held_id, free_id],
            as_of=stored_due + timedelta(seconds=1),
        )
    assert free_id in disposed, "the eligible document was not disposed, so this proves nothing"
    assert held_id not in disposed, "a held document was named for disposal and accepted"

    async with async_session_maker() as session:
        survivor = await session.scalar(select(Document.id).where(Document.id == held_id))
        assert survivor is not None, "a held document was hard-deleted by disposal"


@pytest.mark.asyncio
async def test_register_reports_the_hold_and_the_matter(
    admin_client: AsyncClient,
    superuser_client: AsyncClient,
) -> None:
    matter = f"MATTER-{uuid.uuid4().hex[:8]}"
    document_id = await _seed_document()
    await _file_under_matter(superuser_client, document_id, matter)
    await _issue_hold(superuser_client, matter)

    detail = await admin_client.get(f"/api/v1/documents/{document_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["legal_hold_active"] is True
    assert detail.json()["legal_matter_reference"] == matter

    listing = await admin_client.get(f"/api/v1/documents/?search={matter[-8:]}&page_size=100")
    assert listing.status_code == 200, listing.text
    rows = {int(item["id"]): item for item in listing.json()["items"]}
    if document_id in rows:
        assert rows[document_id]["legal_hold_active"] is True


@pytest.mark.asyncio
async def test_taking_a_document_out_of_a_matter_is_recorded(superuser_client: AsyncClient) -> None:
    """The one call that can unfreeze a record must leave a trace of who did it."""
    from src.domain.models.audit_log import AuditLogEntry

    matter = f"MATTER-{uuid.uuid4().hex[:8]}"
    document_id = await _seed_document()
    await _file_under_matter(superuser_client, document_id, matter)
    await _issue_hold(superuser_client, matter)
    await _file_under_matter(superuser_client, document_id, None)

    async with async_session_maker() as session:
        rows = list(
            (
                await session.execute(
                    select(AuditLogEntry).where(
                        AuditLogEntry.entity_type == "document",
                        AuditLogEntry.entity_id == str(document_id),
                    )
                )
            )
            .scalars()
            .all()
        )

    scope_events = [
        row for row in rows if (row.entry_metadata or {}).get("event_type") == "document.legal_hold_scope_changed"
    ]
    assert len(scope_events) == 2, f"expected the filing and the removal to be recorded, got {len(scope_events)}"

    removal = [row for row in scope_events if (row.new_values or {}).get("matter_reference") is None]
    assert len(removal) == 1, [row.new_values for row in scope_events]
    assert removal[0].new_values["previous_matter_reference"] == matter
    assert removal[0].user_id == 2, "the removal was not attributed to the caller"
    assert "legal_matter_reference" in (removal[0].changed_fields or [])


@pytest.mark.asyncio
async def test_hold_scope_write_requires_hold_administration(admin_client: AsyncClient) -> None:
    """``document:update`` must not be able to file a record out of a hold's scope."""
    document_id = await _seed_document()
    res = await admin_client.put(
        f"/api/v1/legal-holds/documents/{document_id}",
        json={"matter_reference": "MATTER-ESCALATION"},
    )
    assert res.status_code == 403, f"expected 403 for a non-hold-admin, got {res.status_code} {res.text}"


@pytest.mark.asyncio
async def test_hold_scope_write_rejects_a_document_in_another_tenant(superuser_client: AsyncClient) -> None:
    res = await superuser_client.put(
        "/api/v1/legal-holds/documents/98765432",
        json={"matter_reference": "MATTER-NOWHERE"},
    )
    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# 2. One Register — control folded onto it (L-01d)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_control_record_anchors_to_a_register_row_and_only_once(
    admin_client: AsyncClient,
) -> None:
    document_id = await _seed_document()
    payload = {
        "library_document_id": document_id,
        "title": "WC-1 anchored controlled policy",
        "document_type": "policy",
        "category": "policies",
    }

    first = await admin_client.post("/api/v1/document-control/", json=payload)
    assert first.status_code == 201, first.text

    second = await admin_client.post("/api/v1/document-control/", json=payload)
    assert second.status_code == 409, f"a second control record was allowed on one Register row: {second.text}"
    body = second.json()
    assert (body.get("error", body)).get("code") == "CONTROL_RECORD_EXISTS", body


@pytest.mark.asyncio
async def test_control_record_refuses_an_unknown_anchor(admin_client: AsyncClient) -> None:
    res = await admin_client.post(
        "/api/v1/document-control/",
        json={
            "library_document_id": 98765432,
            "title": "WC-1 dangling anchor policy",
            "document_type": "policy",
            "category": "policies",
        },
    )
    assert res.status_code == 404, f"a control record was anchored to a document nobody has: {res.text}"


@pytest.mark.asyncio
async def test_register_projects_the_control_state_of_its_anchor(admin_client: AsyncClient) -> None:
    document_id = await _seed_document()
    controlled_id = await _seed_controlled(library_document_id=document_id, status="draft")

    detail = await admin_client.get(f"/api/v1/documents/{document_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["controlled_document_id"] == controlled_id
    assert detail.json()["control_status"] == "draft"


@pytest.mark.asyncio
async def test_register_reports_no_control_state_when_nothing_is_anchored(admin_client: AsyncClient) -> None:
    """``null`` rather than ``"draft"``: not under control is a different fact."""
    document_id = await _seed_document()
    detail = await admin_client.get(f"/api/v1/documents/{document_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["controlled_document_id"] is None
    assert detail.json()["control_status"] is None


@pytest.mark.asyncio
async def test_library_publish_moves_the_anchored_control_record(admin_client: AsyncClient) -> None:
    document_id = await _seed_document()
    await _seed_draft_version(document_id)
    controlled_id = await _seed_controlled(library_document_id=document_id, status="draft")

    published = await admin_client.post(f"/api/v1/documents/{document_id}/publish")
    assert published.status_code == 200, published.text

    controlled = await _controlled_row(controlled_id)
    assert controlled.status == "published", "Document Control still reports draft for a published Register row"
    assert controlled.effective_date is not None
    assert controlled.approver_id is None, "publishing invented an approval that never happened"


@pytest.mark.asyncio
async def test_a_publish_does_not_overwrite_who_approved() -> None:
    """The publisher is not the approver, and must not be recorded as one.

    Driven at the service boundary because the two decisions have to be applied in
    sequence to the same control record, which no single endpoint call does.
    """
    from src.domain.services.gkb_control_library_link import write_library_decision_through_to_control

    document_id = await _seed_document()
    controlled_id = await _seed_controlled(library_document_id=document_id)
    # Real user rows: `controlled_documents.approver_id` is a foreign key.
    approver_id = await _author_id()
    publisher_id = 1

    async with async_session_maker() as session:
        document = await session.scalar(select(Document).where(Document.id == document_id))
        assert document is not None
        await write_library_decision_through_to_control(
            session,
            document,
            library_status="approved",
            version_number="1.0",
            actor_id=approver_id,
            actor_name="Approving Manager",
        )
        await write_library_decision_through_to_control(
            session,
            document,
            library_status="published",
            version_number="1.1",
            actor_id=publisher_id,
            actor_name="Publishing Admin",
        )
        await session.commit()

    controlled = await _controlled_row(controlled_id)
    assert controlled.status == "published"
    assert controlled.current_version == "1.1"
    assert controlled.approver_id == approver_id, "the publisher replaced the approver on the control record"
    assert controlled.approver_name == "Approving Manager"


@pytest.mark.asyncio
async def test_author_cannot_publish_their_own_document(admin_client: AsyncClient) -> None:
    """L-40 separation of duties on the one path that had none."""
    document_id = await _seed_document(created_by_id=1)
    await _seed_draft_version(document_id)

    res = await admin_client.post(f"/api/v1/documents/{document_id}/publish")
    assert res.status_code == 400, f"an author published their own document: {res.status_code} {res.text}"
    body = res.json()
    assert (body.get("error", body)).get("code") == "SEPARATION_OF_DUTIES", body

    async with async_session_maker() as session:
        row = await session.scalar(select(Document).where(Document.id == document_id))
        assert row is not None
        assert row.status != DocumentStatus.PUBLISHED, "the refused publish was applied anyway"
