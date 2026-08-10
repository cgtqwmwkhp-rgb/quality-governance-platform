"""``GET /api/v1/approvals/my-decisions`` against a real database.

Two things are pinned, and the second is the reason the file uses a scratch
database rather than the shared harness.

**What the endpoint returns.** A decision reaches the caller's queue only when a
domain names them on it — no role expansion, no tenant-wide queue — and a
decision that names nobody is counted rather than dropped.

**What it says when it cannot look.** ``document_approval_instances`` and
``document_approval_workflows`` were absent from every Alembic-built schema until
``20260906_doc_ctl_children`` (``docs/governance/alembic_check_excluded_tables.md``),
so any deployment behind that revision still cannot read them. That source must
then report itself *unreadable*, never *empty*, and the distinction has to survive
the trip to the client: an empty ``items`` beside ``sources_complete: true`` is a
promise that nothing is waiting. The shared integration harness runs ``create_all``
and so structurally cannot host that case, which is how endpoints that could not
work against the real schema came to ship green — hence ``doc_control_scratch``,
which drops the tables with real DDL.

The last class pins the deletions this endpoint replaces. Those four approval
endpoints did not merely return nothing: ``POST /workflows/approvals/{id}/approve``
answered ``{"status": "approved"}`` without writing anywhere, and
``GET /workflows/delegations`` handed every caller the same invented
"Jane Smith / Annual leave" record.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pytest
from httpx import AsyncClient

from tests.integration._document_control_scratch import TENANT_ID, USER_ID, ScratchDatabase

ENDPOINT = "/api/v1/approvals/my-decisions"

OTHER_USER_ID = USER_ID + 4242
OTHER_TENANT_ID = TENANT_ID + 77


def _naive_utc(offset_days: int = 0) -> datetime:
    """Every ``DateTime`` column touched here is declared without ``timezone=True``.

    asyncpg refuses to adapt an aware datetime for ``timestamp without time
    zone`` and raises, and SQLite does not reproduce it — so a test written with
    aware datetimes passes locally and fails only on Postgres.
    """
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).replace(tzinfo=None)


async def _seed_document_approval(
    scratch: ScratchDatabase,
    *,
    workflow_steps: list[Any],
    current_step: int = 1,
    status: str = "pending",
    tenant_id: int = TENANT_ID,
    title: str = "Controlled procedure awaiting a decision",
    due_in_days: Optional[int] = 3,
) -> tuple[int, int]:
    """Insert a controlled document and a pending approval instance on it.

    Returns ``(document_id, instance_id)``.
    """
    from src.domain.models.document_control import (
        ControlledDocument,
        DocumentApprovalInstance,
        DocumentApprovalWorkflow,
    )

    async with scratch.sessions() as session:
        document = ControlledDocument(
            tenant_id=tenant_id,
            document_number=f"DOC-{uuid.uuid4().hex[:10]}",
            title=title,
            document_type="procedure",
            category="quality",
            status="pending_approval",
        )
        workflow = DocumentApprovalWorkflow(
            tenant_id=tenant_id,
            name="Two-step procedure approval",
            applicable_document_types=["procedure"],
            workflow_steps=workflow_steps,
        )
        session.add_all([document, workflow])
        await session.flush()

        instance = DocumentApprovalInstance(
            tenant_id=tenant_id,
            document_id=document.id,
            workflow_id=workflow.id,
            current_step=current_step,
            status=status,
            initiated_date=_naive_utc(-1),
            due_date=_naive_utc(due_in_days) if due_in_days is not None else None,
        )
        session.add(instance)
        await session.commit()
        return document.id, instance.id


async def _seed_signature_request(
    scratch: ScratchDatabase,
    *,
    signer_user_id: Optional[int],
    signer_email: str,
    request_status: str = "pending",
    signer_status: str = "pending",
    tenant_id: int = TENANT_ID,
    title: str = "Annual policy pack",
) -> int:
    from src.domain.models.digital_signature import SignatureRequest, SignatureRequestSigner

    async with scratch.sessions() as session:
        request = SignatureRequest(
            tenant_id=tenant_id,
            reference_number=f"SIG-{uuid.uuid4().hex[:10]}",
            title=title,
            document_type="policy",
            status=request_status,
            initiated_by_id=USER_ID,
            created_at=_naive_utc(-2),
            expires_at=_naive_utc(10),
        )
        session.add(request)
        await session.flush()

        session.add(
            SignatureRequestSigner(
                request_id=request.id,
                user_id=signer_user_id,
                email=signer_email,
                name="Signer",
                status=signer_status,
                order=1,
            )
        )
        await session.commit()
        return request.id


async def _seed_investigation(
    scratch: ScratchDatabase,
    *,
    reviewer_user_id: Optional[int],
    status: str = "under_review",
    tenant_id: int = TENANT_ID,
    title: str = "Investigation waiting on my review",
) -> int:
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun, InvestigationTemplate

    async with scratch.sessions() as session:
        template = InvestigationTemplate(
            name=f"Template {uuid.uuid4().hex[:8]}",
            description="Seeded for the my-decisions read model",
            version="1.0",
            structure={"sections": []},
            applicable_entity_types=["reporting_incident"],
            tenant_id=tenant_id,
        )
        session.add(template)
        await session.flush()

        investigation = InvestigationRun(
            tenant_id=tenant_id,
            template_id=template.id,
            assigned_entity_type=AssignedEntityType.REPORTING_INCIDENT,
            # Unique per row: investigation_runs carries a uniqueness constraint
            # over the assigned entity within a tenant.
            assigned_entity_id=uuid.uuid4().int % 10_000_000,
            title=title,
            reference_number=f"INV-{uuid.uuid4().hex[:10]}",
            status=status,
            reviewer_user_id=reviewer_user_id,
        )
        session.add(investigation)
        await session.commit()
        return investigation.id


async def _caller_email() -> str:
    """The address the endpoint under test will see for this caller.

    Built through the harness's own resolver rather than hardcoded, because that
    resolver takes the address from whichever user row carries the token subject in
    the *main* test database — not the scratch one this test writes to — and falls
    back to a synthetic address when there is no such row. Asserting against a
    guess would either pass vacuously or fail for a reason that has nothing to do
    with this endpoint.
    """
    from sqlalchemy import select as sa_select

    from src.domain.models.user import User
    from src.infrastructure.database import async_session_maker
    from tests.integration.conftest import _mock_user_from_jwt

    async with async_session_maker() as session:
        db_user = (await session.execute(sa_select(User).where(User.id == USER_ID))).scalar_one_or_none()

    caller = _mock_user_from_jwt({"sub": str(USER_ID), "tenant_id": TENANT_ID, "role": "admin"}, db_user=db_user)
    email = str(caller.email)
    assert "@" in email, "the caller has no address, so the by-email signer path cannot be exercised"
    return email


def _source(body: dict, key: str) -> dict:
    matching = [source for source in body["sources"] if source["key"] == key]
    assert matching, f"{key} is not reported at all; sources={body['sources']}"
    return matching[0]


class TestTheHarnessCanObserveTheProductionShape:
    """Without this, every assertion about absent tables could pass vacuously."""

    async def test_the_scratch_schema_starts_with_the_approval_tables(self, doc_control_scratch: ScratchDatabase):
        assert await doc_control_scratch.has_table("document_approval_instances") is True
        assert await doc_control_scratch.has_table("document_approval_workflows") is True

    async def test_the_harness_really_loses_them(self, doc_control_scratch: ScratchDatabase):
        await doc_control_scratch.drop_tables()

        assert await doc_control_scratch.has_table("document_approval_instances") is False
        assert await doc_control_scratch.has_table("document_approval_workflows") is False


class TestDocumentApprovalsThatAreMine:
    async def test_an_approval_naming_me_on_the_current_step_is_listed(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        document_id, instance_id = await _seed_document_approval(
            doc_control_scratch,
            workflow_steps=[{"level": 1, "approvers": [USER_ID]}, {"level": 2, "approvers": [OTHER_USER_ID]}],
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert response.status_code == 200, response.text
        body = response.json()
        keys = [item["key"] for item in body["items"]]
        assert f"document_approval:{instance_id}" in keys
        item = next(item for item in body["items"] if item["key"] == f"document_approval:{instance_id}")
        assert item["decision"] == "approve"
        assert item["title"] == "Controlled procedure awaiting a decision"
        assert item["deep_link"] == f"/document-control?document={document_id}"
        assert item["due_at"] is not None

    async def test_an_approval_waiting_on_a_later_step_that_names_me_is_not_mine_yet(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """Step 2's approver owes nothing until step 1 has decided."""
        _, instance_id = await _seed_document_approval(
            doc_control_scratch,
            workflow_steps=[{"level": 1, "approvers": [OTHER_USER_ID]}, {"level": 2, "approvers": [USER_ID]}],
            current_step=1,
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert response.status_code == 200, response.text
        assert f"document_approval:{instance_id}" not in [item["key"] for item in response.json()["items"]]

    async def test_an_approval_naming_somebody_else_is_not_listed(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        _, instance_id = await _seed_document_approval(
            doc_control_scratch,
            workflow_steps=[{"level": 1, "approvers": [OTHER_USER_ID]}],
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        body = response.json()
        assert f"document_approval:{instance_id}" not in [item["key"] for item in body["items"]]
        assert _source(body, "document_approval")["count"] == 0

    async def test_an_already_decided_instance_is_not_listed(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        _, instance_id = await _seed_document_approval(
            doc_control_scratch,
            workflow_steps=[{"level": 1, "approvers": [USER_ID]}],
            status="approved",
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert f"document_approval:{instance_id}" not in [item["key"] for item in response.json()["items"]]

    async def test_another_tenants_approval_naming_my_user_id_is_not_listed(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """User ids are not unique across tenants; the queue must be tenant-scoped."""
        _, instance_id = await _seed_document_approval(
            doc_control_scratch,
            workflow_steps=[{"level": 1, "approvers": [USER_ID]}],
            tenant_id=OTHER_TENANT_ID,
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert f"document_approval:{instance_id}" not in [item["key"] for item in response.json()["items"]]

    async def test_an_approval_naming_nobody_is_counted_rather_than_dropped(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """A step with no approvers is outstanding for nobody — a configuration defect.

        It must not appear in this caller's queue, and it must not disappear: the
        only place it would otherwise be visible is the register it is stuck in.
        """
        await _seed_document_approval(
            doc_control_scratch,
            workflow_steps=[{"level": 1, "role": "quality-manager"}],
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        body = response.json()
        assert body["items"] == []
        source = _source(body, "document_approval")
        assert source["status"] == "live"
        assert source["count"] == 0
        assert source["unattributed"] == 1


class TestInvestigationReviewsThatAreMine:
    """The one source that is end to end today: real row, real screen, real action.

    ``PATCH /api/v1/investigations/{id}`` sets ``reviewer_user_id`` and
    ``under_review``; ``POST /api/v1/investigations/{id}/approve`` is the decision
    that clears the row from this list.
    """

    async def test_an_investigation_naming_me_as_reviewer_is_listed(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        investigation_id = await _seed_investigation(doc_control_scratch, reviewer_user_id=USER_ID)

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert response.status_code == 200, response.text
        body = response.json()
        item = next(item for item in body["items"] if item["key"] == f"investigation_review:{investigation_id}")
        assert item["decision"] == "review"
        assert item["deep_link"] == f"/investigations/{investigation_id}"
        assert item["requested_at_basis"] == "last_updated", (
            "the move into under_review is not timestamped on the row, so the date shown must not "
            "be labelled as when the review was requested"
        )

    async def test_an_investigation_naming_somebody_else_is_not_mine(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        investigation_id = await _seed_investigation(doc_control_scratch, reviewer_user_id=OTHER_USER_ID)

        response = await doc_control_scratch_client.get(ENDPOINT)

        body = response.json()
        assert f"investigation_review:{investigation_id}" not in [item["key"] for item in body["items"]]
        assert _source(body, "investigation_review")["count"] == 0

    async def test_an_investigation_with_no_reviewer_is_counted_not_dropped(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """``reviewer_user_id`` is nullable, and a null reviewer names nobody.

        This read model will not guess who — there is no role expansion here — but
        it does not stay quiet either: an unassigned review is waiting on somebody
        the row does not identify, so it is reported on the source exactly as an
        approval step with no approvers is.
        """
        investigation_id = await _seed_investigation(doc_control_scratch, reviewer_user_id=None)

        response = await doc_control_scratch_client.get(ENDPOINT)

        body = response.json()
        assert f"investigation_review:{investigation_id}" not in [item["key"] for item in body["items"]]
        source = _source(body, "investigation_review")
        assert source["status"] == "live"
        assert source["count"] == 0
        assert source["unattributed"] == 1

    async def test_an_investigation_not_under_review_is_not_a_decision_yet(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """Being named reviewer on work still in progress is not an outstanding decision."""
        investigation_id = await _seed_investigation(
            doc_control_scratch, reviewer_user_id=USER_ID, status="in_progress"
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert f"investigation_review:{investigation_id}" not in [item["key"] for item in response.json()["items"]]

    async def test_another_tenants_investigation_naming_my_user_id_is_not_listed(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        investigation_id = await _seed_investigation(
            doc_control_scratch, reviewer_user_id=USER_ID, tenant_id=OTHER_TENANT_ID
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert f"investigation_review:{investigation_id}" not in [item["key"] for item in response.json()["items"]]


class TestSignaturesThatAreMine:
    async def test_a_request_awaiting_my_signature_is_listed(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        request_id = await _seed_signature_request(
            doc_control_scratch,
            signer_user_id=USER_ID,
            signer_email="someone-else@example.com",
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert response.status_code == 200, response.text
        item = next(item for item in response.json()["items"] if item["key"] == f"signature_request:{request_id}")
        assert item["decision"] == "sign"
        assert item["deep_link"] is None, (
            "/signatures renders a hardcoded empty list and never calls the signatures API, so a "
            "link there would send a user holding real work to a screen claiming they have none"
        )

    async def test_a_signer_matched_only_by_email_is_still_mine(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """Signers may be invited by address before they hold an account."""
        email = await _caller_email()
        request_id = await _seed_signature_request(
            doc_control_scratch,
            signer_user_id=None,
            signer_email=email.upper(),
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert f"signature_request:{request_id}" in [item["key"] for item in response.json()["items"]]

    async def test_a_signature_i_have_already_given_is_not_still_waiting(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        request_id = await _seed_signature_request(
            doc_control_scratch,
            signer_user_id=USER_ID,
            signer_email="anyone@example.com",
            signer_status="signed",
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert f"signature_request:{request_id}" not in [item["key"] for item in response.json()["items"]]

    async def test_a_request_i_have_opened_but_not_signed_is_still_waiting(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """``viewed`` is the case this surface exists for: seen, and not done."""
        request_id = await _seed_signature_request(
            doc_control_scratch,
            signer_user_id=USER_ID,
            signer_email="anyone@example.com",
            signer_status="viewed",
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert f"signature_request:{request_id}" in [item["key"] for item in response.json()["items"]]

    async def test_somebody_elses_signature_is_not_mine(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        request_id = await _seed_signature_request(
            doc_control_scratch,
            signer_user_id=OTHER_USER_ID,
            signer_email="somebody-else@example.com",
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        body = response.json()
        assert f"signature_request:{request_id}" not in [item["key"] for item in body["items"]]
        assert _source(body, "signature_request")["count"] == 0

    async def test_another_tenants_request_naming_my_user_id_is_not_mine(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """The signer row carries a nullable tenant, so the request must be scoped.

        Same reason as the document and investigation cases: user ids are not
        unique across tenants, so an unscoped signer match would put another
        tenant's document in front of this user.
        """
        request_id = await _seed_signature_request(
            doc_control_scratch,
            signer_user_id=USER_ID,
            signer_email="anyone@example.com",
            tenant_id=OTHER_TENANT_ID,
        )

        response = await doc_control_scratch_client.get(ENDPOINT)

        body = response.json()
        assert f"signature_request:{request_id}" not in [item["key"] for item in body["items"]]
        assert _source(body, "signature_request")["count"] == 0

    async def test_one_request_i_am_named_on_twice_is_one_decision(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """A user can be on a request as both an account and an address."""
        from src.domain.models.digital_signature import SignatureRequestSigner

        email = await _caller_email()
        request_id = await _seed_signature_request(
            doc_control_scratch,
            signer_user_id=USER_ID,
            signer_email="account-row@example.com",
        )
        async with doc_control_scratch.sessions() as session:
            session.add(
                SignatureRequestSigner(
                    request_id=request_id,
                    user_id=None,
                    email=email,
                    name="Same person, invited by address",
                    status="pending",
                    order=2,
                )
            )
            await session.commit()

        response = await doc_control_scratch_client.get(ENDPOINT)

        keys = [item["key"] for item in response.json()["items"]]
        assert keys.count(f"signature_request:{request_id}") == 1


class TestASourceThatCouldNotBeRead:
    """The case production is actually in, and the one an empty list would hide."""

    async def test_absent_approval_tables_are_named_rather_than_reported_as_zero(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["sources_complete"] is False
        assert "document_approval" in body["unavailable_sources"]
        source = _source(body, "document_approval")
        assert source["status"] == "unavailable"
        assert source["count"] is None, "an unread source must not report a count of any kind"
        assert "document_approval_instances" in (source["reason"] or "")
        assert "not a report that there are none" in (source["reason"] or "")

    async def test_a_readable_source_still_answers_when_another_is_absent(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """One absent table must not take the rest of the panel down with it.

        On PostgreSQL a SELECT against a missing relation aborts the surrounding
        transaction, so an unguarded read of the approvals tables would make the
        signature read fail too — the failure mode that turned one unreadable
        subordinate list into a dead document-detail page.
        """
        request_id = await _seed_signature_request(
            doc_control_scratch,
            signer_user_id=USER_ID,
            signer_email="anyone@example.com",
        )
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.get(ENDPOINT)

        assert response.status_code == 200, response.text
        body = response.json()
        assert f"signature_request:{request_id}" in [item["key"] for item in body["items"]]
        assert _source(body, "signature_request")["status"] == "live"
        assert body["sources_complete"] is False

    async def test_every_source_answering_is_what_makes_the_reading_complete(
        self, doc_control_scratch_client: AsyncClient
    ):
        response = await doc_control_scratch_client.get(ENDPOINT)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["sources_complete"] is True
        assert body["unavailable_sources"] == []
        assert body["items"] == []
        assert body["total"] == 0
        assert {source["key"] for source in body["sources"]} == {
            "investigation_review",
            "document_approval",
            "signature_request",
        }


class TestEverySourceTogether:
    async def test_decisions_from_three_domains_arrive_in_one_list_soonest_first(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """One list, ordered by deadline, with the undated decision last.

        The point of the panel is that a user reads one list instead of three
        registers, so ordering across domains is part of the contract rather than
        an accident of the order the adapters happen to run in.
        """
        _, instance_id = await _seed_document_approval(
            doc_control_scratch,
            workflow_steps=[{"level": 1, "approvers": [USER_ID]}],
            due_in_days=1,
        )
        signature_id = await _seed_signature_request(
            doc_control_scratch,
            signer_user_id=USER_ID,
            signer_email="anyone@example.com",
        )
        investigation_id = await _seed_investigation(doc_control_scratch, reviewer_user_id=USER_ID)

        response = await doc_control_scratch_client.get(ENDPOINT)

        body = response.json()
        assert body["total"] == 3
        # Approval due tomorrow, signature expiring in ten days, and the
        # investigation review, which carries no deadline at all.
        assert [item["key"] for item in body["items"]] == [
            f"document_approval:{instance_id}",
            f"signature_request:{signature_id}",
            f"investigation_review:{investigation_id}",
        ]


class TestTheFictionThisReplaced:
    """Deleted with this endpoint's arrival. A 404 is the assertion."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("get", "/api/v1/workflows/approvals/pending"),
            ("post", "/api/v1/workflows/approvals/APR-001/approve"),
            ("post", "/api/v1/workflows/approvals/APR-001/reject"),
            ("post", "/api/v1/workflows/approvals/bulk-approve"),
            ("get", "/api/v1/workflows/delegations"),
            ("post", "/api/v1/workflows/delegations"),
            ("delete", "/api/v1/workflows/delegations/DEL-20260115001"),
            ("get", "/api/v1/workflows/stats"),
        ],
    )
    async def test_the_stub_approval_surface_is_gone(self, client: AsyncClient, method: str, path: str):
        response = await client.request(method.upper(), path, json={} if method == "post" else None)

        assert response.status_code == 404, (
            f"{method.upper()} {path} still answers {response.status_code}. It was backed by an "
            "in-memory engine that persisted nothing, so a 200 here is a decision nobody recorded."
        )

    async def test_no_response_anywhere_still_carries_the_invented_delegation(self, client: AsyncClient):
        """The hardcoded record, by the name a user would have read off the screen."""
        response = await client.get("/api/v1/workflows/delegations")

        assert "Jane Smith" not in response.text
        assert "DEL-20260115001" not in response.text
