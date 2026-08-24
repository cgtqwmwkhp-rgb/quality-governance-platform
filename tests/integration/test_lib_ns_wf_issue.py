"""NS-WF / W6 — the issue transition on the HTTP surface it is reached through.

The rule logic is unit-tested against the service; this file proves the route is
actually wired to it, because a guard that is only reachable from a test is not a
guard. Three things are asserted end to end against a real database: an approved
document issues and comes back live, an unapproved one is refused, and an issue
that would break an issue-time rule (R20) is refused with the rule named.

The document is authored by a third user, distinct from ``admin_client`` (user 1),
so the separation-of-duties refusals do not fire incidentally and mask the
assertion under test.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.document import Document, DocumentVersion, FileType
from src.domain.models.enums import DocumentStatus
from src.infrastructure.database import async_session_maker

TENANT = 1
_AUTHOR_EMAIL = "nswf-author@test.example.com"
_APPROVER_ID = 2  # superuser_client; anyone other than the version author


async def _author_id() -> int:
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


async def _seed_approved(
    *,
    status: DocumentStatus = DocumentStatus.APPROVED,
    version_status: str = "approved",
    version_number: str = "2.0",
    change_notes: str | None = "Reissue after annual review",
    review_cycle_months: int | None = 12,
    review_cycle_basis: str | None = "Statutory — Regulatory Reform (Fire Safety) Order 2005",
) -> int:
    author_id = await _author_id()
    async with async_session_maker() as session:
        document = Document(
            tenant_id=TENANT,
            reference_number=f"DOC-{uuid.uuid4().hex[:14]}",
            title=f"NS-WF issue probe {uuid.uuid4().hex[:8]}",
            file_name="nswf-probe.pdf",
            file_type=FileType.PDF,
            file_size=2048,
            file_path=f"seed/nswf/{uuid.uuid4().hex}.pdf",
            status=status,
            version=version_number,
            is_active=True,
            created_by_id=author_id,
            review_cycle_months=review_cycle_months,
            review_cycle_basis=review_cycle_basis,
        )
        session.add(document)
        await session.flush()
        session.add(
            DocumentVersion(
                tenant_id=TENANT,
                document_id=document.id,
                version_number=version_number,
                change_notes=change_notes,
                change_type="revision",
                status=version_status,
                is_immutable=version_status != "draft",
                file_name="nswf-probe.pdf",
                file_path=f"seed/nswf/{uuid.uuid4().hex}.pdf",
                file_size=2048,
                created_by_id=author_id,
                published_by_id=_APPROVER_ID,
            )
        )
        await session.commit()
        return int(document.id)


async def _document_row(document_id: int) -> Document:
    async with async_session_maker() as session:
        row = await session.scalar(select(Document).where(Document.id == document_id))
        assert row is not None
        return row


@pytest.mark.asyncio
async def test_an_approved_document_issues(admin_client: AsyncClient) -> None:
    document_id = await _seed_approved()

    response = await admin_client.post(f"/api/v1/documents/{document_id}/issue")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == DocumentStatus.PUBLISHED.value
    assert response.json()["published_version"] == "2.0"

    row = await _document_row(document_id)
    assert row.status == DocumentStatus.PUBLISHED

    async with async_session_maker() as session:
        version = await session.scalar(select(DocumentVersion).where(DocumentVersion.document_id == document_id))
        assert version is not None
        assert version.status == "published"
        assert version.issued_at is not None
        assert version.published_by_id == _APPROVER_ID, "the issue overwrote who approved the version"


@pytest.mark.asyncio
async def test_a_draft_is_never_issued(admin_client: AsyncClient) -> None:
    """R14's approval leg on the surface a user reaches."""
    document_id = await _seed_approved(status=DocumentStatus.DRAFT, version_status="draft")

    response = await admin_client.post(f"/api/v1/documents/{document_id}/issue")
    assert response.status_code == 409, response.text

    row = await _document_row(document_id)
    assert row.status == DocumentStatus.DRAFT, "the refused issue was applied anyway"


@pytest.mark.asyncio
async def test_an_unstated_review_cycle_refuses_the_issue(admin_client: AsyncClient) -> None:
    document_id = await _seed_approved(review_cycle_months=None, review_cycle_basis=None)

    response = await admin_client.post(f"/api/v1/documents/{document_id}/issue")
    assert response.status_code == 422, response.text
    assert "R20" in response.text

    row = await _document_row(document_id)
    assert row.status == DocumentStatus.APPROVED


@pytest.mark.asyncio
async def test_the_owner_may_state_the_review_cycle_when_issuing(admin_client: AsyncClient) -> None:
    document_id = await _seed_approved(review_cycle_months=None, review_cycle_basis=None)

    response = await admin_client.post(
        f"/api/v1/documents/{document_id}/issue",
        json={"review_cycle_months": 24, "review_cycle_basis": "ISO 9001 certification expectation"},
    )
    assert response.status_code == 200, response.text

    row = await _document_row(document_id)
    assert row.status == DocumentStatus.PUBLISHED
    assert row.review_cycle_months == 24
    assert row.review_cycle_basis == "ISO 9001 certification expectation"
