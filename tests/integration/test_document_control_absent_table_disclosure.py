"""Document control must say which of its tables production does not have.

Seven tables this module reads have no create migration and are absent from
production, verified two ways: an ``information_schema`` read of the production
database, and ``alembic upgrade head`` against a clean PostgreSQL 14, which
produced the same sixteen absent tables repo-wide. All seven are on the deferral
register at ``docs/governance/alembic_check_excluded_tables.md`` marked "migration
coverage pending", so the honest description is not "temporarily broken" but
"never built".

Both classes of endpoint are pinned here, and the distinction between them is the
whole point of the file:

* **A table that exists and is empty is a legitimate answer.** ``TestAReadThatHappened``
  pins that an empty distribution list, an empty workflow list and an empty access
  log all still return ``200`` with ``[]`` and no disclosure attached. Turning a
  genuine empty state into an error would be the mirror image of the defect and
  worse, because it breaks software that works.
* **A table that is absent is not.** ``TestAReadThatCouldNotHappen`` and
  ``TestAWriteThatDidNotHappen`` pin that absence is never expressible as an empty
  list, a zero, or a silent success.

Every test here fails before the change: the endpoints raised ``ProgrammingError``
and answered 500, and the two partially-readable ones took their readable figures
down with them.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from src.domain.error_codes import ErrorCode
from tests.integration._document_control_scratch import (
    ABSENT_IN_PRODUCTION,
    ACCESS_LOG_TABLE,
    DISTRIBUTIONS_TABLE,
    OBSOLETE_TABLE,
    WORKFLOWS_TABLE,
    ScratchDatabase,
)

BASE = "/api/v1/document-control"


async def _create_document(client: AsyncClient) -> int:
    """Create a controlled document. Unaffected by the absent tables."""
    response = await client.post(
        f"{BASE}/",
        json={
            "title": "Disclosure suite controlled procedure",
            "document_type": "procedure",
            "category": "quality",
            "description": "created by test_document_control_absent_table_disclosure",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


class TestTheHarnessCanSeeAMissingTable:
    """Without this, every assertion below could pass vacuously."""

    async def test_the_schema_starts_with_every_declared_table(self, doc_control_scratch: ScratchDatabase):
        for name in ABSENT_IN_PRODUCTION:
            assert await doc_control_scratch.has_table(name) is True, name

    async def test_the_harness_really_loses_the_tables(self, doc_control_scratch: ScratchDatabase):
        await doc_control_scratch.drop_tables()
        for name in ABSENT_IN_PRODUCTION:
            assert await doc_control_scratch.has_table(name) is False, (
                f"the scratch database still has {name}, so this file cannot observe " "the condition it exists to test"
            )


class TestAReadThatHappened:
    """A table that exists and holds nothing keeps answering exactly as before.

    This is the direction that must not regress. Every one of these tables is
    empty in a brand-new tenant, and an empty controlled-copy list is a true and
    ordinary thing to say.
    """

    async def test_an_empty_distribution_list_is_still_an_empty_list(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        document_id = await _create_document(doc_control_scratch_client)

        response = await doc_control_scratch_client.get(f"{BASE}/{document_id}")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["distributions"] == []
        assert "unavailable" not in body, (
            "a table that was read and found empty must not be described as "
            f"unavailable: {body.get('unavailable')!r}"
        )

    async def test_an_empty_workflow_list_is_still_an_empty_list(self, doc_control_scratch_client: AsyncClient):
        response = await doc_control_scratch_client.get(f"{BASE}/workflows")

        assert response.status_code == 200, response.text
        assert response.json() == []

    async def test_an_empty_access_log_is_still_an_empty_list(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        document_id = await _create_document(doc_control_scratch_client)

        response = await doc_control_scratch_client.get(f"{BASE}/{document_id}/access-log")

        assert response.status_code == 200, response.text
        assert response.json() == []

    async def test_a_measured_acknowledgment_count_is_reported_as_a_number(
        self, doc_control_scratch_client: AsyncClient
    ):
        """Zero really is zero when the table was there to be counted."""
        response = await doc_control_scratch_client.get(f"{BASE}/summary")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["pending_acknowledgments"] == 0
        assert "unmeasurable" not in body

    async def test_a_distribution_can_still_be_recorded(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """The write path is untouched while its table is present."""
        document_id = await _create_document(doc_control_scratch_client)

        response = await doc_control_scratch_client.post(
            f"{BASE}/{document_id}/distribute",
            json={"recipient_type": "user", "recipient_name": "Reviewer"},
        )

        assert response.status_code == 201, response.text


class TestTheDocumentDetailPageStaysUsable:
    """The surface behind the Document Control menu item.

    Two subordinate reads were denying access to the whole document: the
    distribution list, and the access-log row this endpoint writes on every view.
    On PostgreSQL the first failed statement aborts the transaction, so the
    ``view_count`` increment staged in the same commit was lost as well.
    """

    async def test_the_document_is_still_served(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        document_id = await _create_document(doc_control_scratch_client)
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.get(f"{BASE}/{document_id}")

        assert response.status_code == 200, (
            "the document, its versions and its metadata are all readable; "
            f"got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert body["id"] == document_id
        assert body["title"] == "Disclosure suite controlled procedure"
        assert body["versions"], "version history comes from a table that exists"

    async def test_the_unreadable_parts_are_named(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        document_id = await _create_document(doc_control_scratch_client)
        await doc_control_scratch.drop_tables()

        body = (await doc_control_scratch_client.get(f"{BASE}/{document_id}")).json()

        assert body["unavailable"]["fields"] == ["access_log", "distributions"]
        assert set(body["unavailable"]["missing_tables"]) == {DISTRIBUTIONS_TABLE, ACCESS_LOG_TABLE}
        assert body["unavailable"]["provisioning_state"] == "migration_pending"

    async def test_the_empty_distribution_list_never_stands_alone(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """The regression that matters most on this endpoint.

        ``distributions`` stays an array because the one consumer reads
        ``detail.distributions.length`` and a missing key would crash the page. An
        empty array is therefore the same bytes as "no controlled copies were
        issued" — a claim this module must not make while the table is gone. The
        array is only safe to send because ``unavailable`` travels with it, so that
        pairing is what is pinned here.
        """
        document_id = await _create_document(doc_control_scratch_client)
        await doc_control_scratch.drop_tables()

        body = (await doc_control_scratch_client.get(f"{BASE}/{document_id}")).json()

        assert body["distributions"] == []
        assert "distributions" in body["unavailable"]["fields"]
        assert DISTRIBUTIONS_TABLE in body["unavailable"]["reasons"]["distributions"] or (
            "distribution" in body["unavailable"]["reasons"]["distributions"]
        )

    async def test_the_view_is_counted_even_though_it_is_not_logged(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """Evidence the commit now happens rather than dying with the transaction."""
        document_id = await _create_document(doc_control_scratch_client)
        await doc_control_scratch.drop_tables()
        before = await doc_control_scratch.view_count(document_id)

        assert (await doc_control_scratch_client.get(f"{BASE}/{document_id}")).status_code == 200

        assert await doc_control_scratch.view_count(document_id) == before + 1

    async def test_a_present_and_empty_read_is_not_described_as_unavailable(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """Both states on one endpoint, so they cannot converge unnoticed."""
        document_id = await _create_document(doc_control_scratch_client)

        readable = (await doc_control_scratch_client.get(f"{BASE}/{document_id}")).json()
        await doc_control_scratch.drop_tables()
        unreadable = (await doc_control_scratch_client.get(f"{BASE}/{document_id}")).json()

        assert readable["distributions"] == unreadable["distributions"] == []
        assert "unavailable" not in readable
        assert "unavailable" in unreadable


class TestAReadThatCouldNotHappen:
    """A list whose only source is absent is never answered with ``[]``."""

    @pytest.mark.parametrize(
        "path_template, table",
        [
            ("{base}/workflows", WORKFLOWS_TABLE),
            ("{base}/{document_id}/access-log", ACCESS_LOG_TABLE),
        ],
    )
    async def test_absence_is_not_a_success(
        self,
        doc_control_scratch: ScratchDatabase,
        doc_control_scratch_client: AsyncClient,
        path_template: str,
        table: str,
    ):
        document_id = await _create_document(doc_control_scratch_client)
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.get(path_template.format(base=BASE, document_id=document_id))

        assert response.status_code == 503, f"{table} absent, yet the endpoint answered {response.status_code}"
        body = response.json()
        assert body["error"]["code"] == ErrorCode.MEASUREMENT_UNAVAILABLE.value
        assert body["error"]["details"]["missing_tables"] == [table]
        assert table in body["error"]["message"]

    @pytest.mark.parametrize(
        "path_template",
        ["{base}/workflows", "{base}/{document_id}/access-log"],
    )
    async def test_no_list_is_offered_when_nothing_was_read(
        self,
        doc_control_scratch: ScratchDatabase,
        doc_control_scratch_client: AsyncClient,
        path_template: str,
    ):
        """A bare array response has no field a caller could misread — as long as
        the body is not an array at all. Both of these declare
        ``response_model=list``, so this is the assertion that the error envelope
        really does replace the array rather than arriving as an empty one."""
        document_id = await _create_document(doc_control_scratch_client)
        await doc_control_scratch.drop_tables()

        body = (await doc_control_scratch_client.get(path_template.format(base=BASE, document_id=document_id))).json()

        assert not isinstance(body, list), f"an unreadable list answered with a list: {body!r}"
        assert "error" in body

    async def test_the_error_is_not_a_generic_server_fault(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """503, not 500: the request is well-formed and the handler is not broken."""
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.get(f"{BASE}/workflows")

        assert response.status_code == 503
        assert response.json()["error"]["code"] != ErrorCode.INTERNAL_ERROR.value
        assert response.json()["error"]["code"] != ErrorCode.DATABASE_ERROR.value


class TestTheSummaryKeepsTheFiguresItCanMeasure:
    """Seven of eight figures come from a table that exists and holds rows.

    Answering 503 would discard those seven to protect the eighth, which is the
    trade PR #1402 already rejected on the acknowledgment dashboard.
    """

    async def test_the_measurable_figures_are_still_served(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        await _create_document(doc_control_scratch_client)
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.get(f"{BASE}/summary")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total_documents"] == 1
        assert body["draft"] == 1
        for key in ("active", "pending_approval", "overdue_review", "obsolete", "by_type"):
            assert key in body, key

    async def test_the_unmeasurable_figure_is_absent_rather_than_zero(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """``0`` here is the exact defect #1402 fixed: an audit reading of a
        measurement that was never taken. ``null`` is barely better — a client
        writing ``pending_acknowledgments ?? 0`` rebuilds the same lie from it —
        so the key is omitted entirely."""
        await doc_control_scratch.drop_tables()

        body = (await doc_control_scratch_client.get(f"{BASE}/summary")).json()

        assert body.get("pending_acknowledgments") != 0
        assert "pending_acknowledgments" not in body, (
            "an unmeasurable count was still offered under its own key: " f"{body.get('pending_acknowledgments')!r}"
        )

    async def test_the_unmeasurable_figure_is_named(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        await doc_control_scratch.drop_tables()

        body = (await doc_control_scratch_client.get(f"{BASE}/summary")).json()

        unmeasurable: dict[str, Any] = body["unmeasurable"]["pending_acknowledgments"]
        assert unmeasurable["missing_tables"] == [DISTRIBUTIONS_TABLE]
        assert unmeasurable["provisioning_state"] == "migration_pending"
        assert "not a count of zero" in unmeasurable["reason"]


class TestAWriteThatDidNotHappen:
    """A refused write says so, and leaves nothing half-applied."""

    async def test_distributing_says_nothing_was_saved(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        document_id = await _create_document(doc_control_scratch_client)
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.post(
            f"{BASE}/{document_id}/distribute",
            json={"recipient_type": "user", "recipient_name": "Reviewer"},
        )

        assert response.status_code == 503, response.text
        body = response.json()
        assert body["error"]["code"] == ErrorCode.FEATURE_NOT_PROVISIONED.value
        assert body["error"]["details"]["missing_tables"] == [DISTRIBUTIONS_TABLE]
        assert body["error"]["details"]["provisioning_state"] == "migration_pending"
        assert "Nothing was saved" in body["error"]["message"]

    async def test_a_refused_write_is_not_reported_as_a_measurement(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """The reason the write code is its own symbol: a caller waiting on a POST
        needs to know their action was not recorded, which is a different fact
        from a figure being unknown."""
        document_id = await _create_document(doc_control_scratch_client)
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.post(
            f"{BASE}/{document_id}/distribute",
            json={"recipient_type": "user", "recipient_name": "Reviewer"},
        )

        assert response.json()["error"]["code"] != ErrorCode.MEASUREMENT_UNAVAILABLE.value

    async def test_submitting_for_approval_leaves_the_document_alone(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """``document.status`` was set to ``pending_approval`` in the same
        transaction as the approval instance. Refusing before touching the
        document is what stops the register showing a document awaiting an
        approval that no table can hold."""
        document_id = await _create_document(doc_control_scratch_client)
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.post(
            f"{BASE}/{document_id}/submit-for-approval",
            params={"workflow_id": 1},
        )

        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == ErrorCode.FEATURE_NOT_PROVISIONED.value
        status, is_current = await doc_control_scratch.document_status(document_id)
        assert status == "draft", f"a refused submission still moved the document to {status!r}"
        assert is_current is True

    async def test_obsoleting_leaves_the_document_current(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """Obsoleting a controlled document without its retention record would
        satisfy the request and lose the reason the record exists, so the honest
        outcome is that nothing moves."""
        document_id = await _create_document(doc_control_scratch_client)
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.post(
            f"{BASE}/{document_id}/obsolete",
            json={"obsolete_reason": "superseded by a newer controlled procedure"},
        )

        assert response.status_code == 503, response.text
        assert response.json()["error"]["details"]["missing_tables"] == [OBSOLETE_TABLE]
        status, is_current = await doc_control_scratch.document_status(document_id)
        assert status == "draft", f"a refused obsoletion still set status to {status!r}"
        assert is_current is True

    async def test_creating_a_workflow_is_refused(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.post(
            f"{BASE}/workflows",
            json={
                "name": "Two-step quality approval",
                "applicable_document_types": ["procedure"],
                "workflow_steps": [{"step": 1, "approver_role": "quality_manager"}],
            },
        )

        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == ErrorCode.FEATURE_NOT_PROVISIONED.value

    async def test_taking_an_approval_decision_is_refused(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.post(
            f"{BASE}/approvals/1/action",
            json={"action": "approved", "comments": "looks fine"},
        )

        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == ErrorCode.FEATURE_NOT_PROVISIONED.value

    async def test_acknowledging_a_distribution_is_refused(
        self, doc_control_scratch: ScratchDatabase, doc_control_scratch_client: AsyncClient
    ):
        """Unreachable through the UI while the list is empty, but reachable by
        anyone holding an old link or driving the API directly, and a 200 here
        would claim an acknowledgment had been recorded."""
        document_id = await _create_document(doc_control_scratch_client)
        await doc_control_scratch.drop_tables()

        response = await doc_control_scratch_client.post(f"{BASE}/{document_id}/distributions/1/acknowledge")

        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == ErrorCode.FEATURE_NOT_PROVISIONED.value
