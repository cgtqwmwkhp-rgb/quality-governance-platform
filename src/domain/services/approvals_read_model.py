"""What decisions are actually waiting on the signed-in user, read from the domains.

Why this is a read model over domains and not a workflow engine
---------------------------------------------------------------
The product already had a generic approvals surface: ``src/api/routes/workflows.py``
on top of the in-memory ``WorkflowTemplateEngine``. It held no state, so its queue
was ``[]`` for every user forever and its "approve" recorded nothing. Replacing it
with a second, better engine would repeat the mistake — an engine only knows about
approvals that were started inside it, and nothing in this product starts them
there. Every real pending decision in this codebase lives in the domain that
raised it.

So this module owns no table and no state. It asks each domain that can answer
"is a decision from this user outstanding here?", and returns what came back
together with an account of which domains could not be asked. Adding a domain
means writing an adapter; nothing is inferred generically from a model's shape,
because "has a status column called pending" is not the same claim as "somebody
owes a decision on this".

The three sources, and what makes each of them real
---------------------------------------------------
``investigation_review``
    ``investigation_runs.status = 'under_review'`` with ``reviewer_user_id``
    naming the caller. ``PATCH /api/v1/investigations/{id}`` sets both, and
    ``POST /api/v1/investigations/{id}/approve`` is the decision that clears it.
    End to end: the data is provisioned, the reviewer is named on the row, and
    ``/investigations/{id}`` is a live screen where the decision can be taken.

``document_approval``
    ``document_approval_instances.status = 'pending'`` whose current workflow step
    names the caller in its ``approvers`` list.
    ``POST /api/v1/document-control/{id}/submit-for-approval`` creates the
    instance; ``POST /api/v1/document-control/approvals/{instance_id}/action`` is
    the decision. The tables were absent from production until
    ``20260906_doc_ctl_children``; the presence check below is kept because a
    deployment behind that revision has to say it cannot see them rather than that
    there are none.

``signature_request``
    ``signature_requests`` in ``pending``/``in_progress`` with a signer row for
    the caller that is not yet signed. Real, provisioned and outstanding — but it
    carries no deep link, because ``frontend/src/pages/DigitalSignatures.tsx``
    renders a hardcoded empty list and never calls the signatures API. Sending
    someone holding real work to a screen that tells them they have none would be
    worse than sending them nowhere, and dropping the rows would be worse still.

Why an unanswerable source is reported rather than skipped
----------------------------------------------------------
The dangerous failure for this surface is not an error, it is a confident empty
list: "nothing needs you" is a sentence a user acts on by going home. Two
different things produce zero rows and they must not look alike:

* the domain was read and holds nothing for this user — a measurement;
* the domain could not be read at all — not a measurement.

:class:`SourceReading` carries that distinction per source, and
:attr:`MyDecisions.sources_complete` lets a caller refuse to render "you are
clear" while any source is unread. One unreadable source does not fail the
request, because that would take down the queues that *can* be read.

Why attribution is narrow on purpose
------------------------------------
An item appears here only when the user is named on the record. There is no role
expansion, no "anyone in this department may approve", and no delegation: those
are policy decisions this read model is not entitled to invent, and inventing them
would put another person's work in your queue. A pending approval whose current
step names nobody is therefore not silently dropped — it cannot be attributed to
*anyone*, which is a defect in the workflow configuration, so it is counted and
reported on the source (:attr:`SourceReading.unattributed`) instead of vanishing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.digital_signature import SignatureRequest, SignatureRequestSigner
from src.domain.models.document_control import ControlledDocument, DocumentApprovalInstance, DocumentApprovalWorkflow
from src.domain.models.investigation import InvestigationRun, InvestigationStatus
from src.domain.services.schema_presence import absent_tables

#: Source keys. Stable strings: the frontend keys its per-source copy off these,
#: and an operator reads them out of ``unavailable_sources`` during an incident.
SOURCE_INVESTIGATION_REVIEW = "investigation_review"
SOURCE_DOCUMENT_APPROVAL = "document_approval"
SOURCE_SIGNATURE_REQUEST = "signature_request"

#: What a date on this row actually means. Carried per item because the three
#: domains record different things, and a column labelled "requested" that is
#: really "last touched" is a small lie that a reader cannot detect.
BASIS_SUBMITTED = "submitted"
BASIS_RAISED = "raised"
BASIS_LAST_UPDATED = "last_updated"

#: Most rows one source contributes. A queue longer than this is a backlog to work
#: through on the owning register, not something to scroll in a panel, and an
#: uncapped query here is a slow page waiting for a busy tenant.
#: :attr:`SourceReading.truncated` says when the cap bit, so a count is never
#: quietly wrong.
MAX_ITEMS_PER_SOURCE = 50

#: Statuses a signature request must hold for a signature on it to be outstanding.
_SIGNATURE_REQUEST_OPEN_STATUSES = ("pending", "in_progress")
#: Statuses *this signer's* row must hold. ``viewed`` is still outstanding — the
#: user opened the request and did not sign it, which is exactly the case this
#: surface exists to keep visible.
_SIGNATURE_SIGNER_OPEN_STATUSES = ("pending", "viewed")


@dataclass(frozen=True)
class PendingDecision:
    """One outstanding decision, attributed to the caller by the owning domain."""

    #: ``{source}:{id}`` — stable within a source, used as a list key and for
    #: deduplication. Not an id in any table on its own.
    key: str
    source: str
    source_label: str
    #: The verb the owning domain uses, so the row can say what is being asked
    #: rather than flattening everything to "approve".
    decision: str
    title: str
    #: Human-facing identifier of the record (document number, request reference).
    reference: Optional[str]
    requested_at: Optional[datetime]
    #: What :attr:`requested_at` is a record of. ``None`` when there is no date.
    requested_at_basis: Optional[str]
    due_at: Optional[datetime]
    #: Route to the screen that owns the record, or ``None`` when this product has
    #: no screen that reads it. ``None`` is a fact about the frontend and is
    #: rendered as such — it is never replaced with a plausible-looking route.
    deep_link: Optional[str]


@dataclass(frozen=True)
class SourceReading:
    """Whether a domain could be asked, and what it said."""

    key: str
    label: str
    #: ``"live"`` — read successfully; ``count`` is a measurement.
    #: ``"unavailable"`` — not read; ``count`` is ``None`` and means nothing.
    status: str
    count: Optional[int]
    #: Why the source is unavailable, in terms an operator can act on.
    reason: Optional[str] = None
    #: Rows this source holds that name no approver on their current step, so they
    #: are outstanding for nobody. Reported because the alternative is a decision
    #: that no queue anywhere shows.
    unattributed: int = 0
    #: True when :data:`MAX_ITEMS_PER_SOURCE` cut the list short, so ``count`` is a
    #: floor for this source rather than its total.
    truncated: bool = False

    @property
    def is_live(self) -> bool:
        return self.status == "live"


@dataclass(frozen=True)
class MyDecisions:
    """The aggregate: attributed items, plus an account of every source asked."""

    items: tuple[PendingDecision, ...]
    sources: tuple[SourceReading, ...]

    @property
    def total(self) -> int:
        """Rows in :attr:`items`.

        A floor rather than a total whenever :attr:`sources_complete` is false or
        any source was truncated.
        """
        return len(self.items)

    @property
    def sources_complete(self) -> bool:
        return all(source.is_live for source in self.sources)

    @property
    def unavailable_sources(self) -> tuple[str, ...]:
        return tuple(source.key for source in self.sources if not source.is_live)


def approvers_for_step(workflow_steps: Any, step_number: int) -> tuple[frozenset[int], bool]:
    """Which user ids may decide ``step_number``, and whether that could be read.

    ``DocumentApprovalWorkflow.workflow_steps`` is free-form JSON — the model
    documents the intended shape in a comment and the database enforces none of
    it — so every access here is defensive. The second element of the return is
    the honest part: ``False`` means the step could not be resolved to any user,
    which is different from resolving it to a set that excludes the caller.

    ``step_number`` is 1-based, matching ``DocumentApprovalInstance.current_step``.
    """
    if not isinstance(workflow_steps, Sequence) or isinstance(workflow_steps, (str, bytes)):
        return frozenset(), False
    if step_number < 1 or step_number > len(workflow_steps):
        return frozenset(), False

    step = workflow_steps[step_number - 1]
    if not isinstance(step, dict):
        return frozenset(), False

    raw = step.get("approvers")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return frozenset(), False

    ids: set[int] = set()
    for entry in raw:
        # Ids arrive as ints from the API and as strings from hand-written JSON.
        # bool is an int subclass and is never a user id.
        if isinstance(entry, bool):
            continue
        if isinstance(entry, int):
            ids.add(entry)
        elif isinstance(entry, str) and entry.strip().lstrip("-").isdigit():
            ids.add(int(entry.strip()))

    # An empty or entirely unusable approver list is a step nobody can act on,
    # which is the unattributed case, not "not yours".
    return frozenset(ids), bool(ids)


def _unavailable(key: str, label: str, absent: tuple[str, ...], what: str) -> SourceReading:
    """The reading for a source whose tables this database does not carry."""
    return SourceReading(
        key=key,
        label=label,
        status="unavailable",
        count=None,
        reason=(
            f"{', '.join(absent)} {'is' if len(absent) == 1 else 'are'} absent from this "
            f"database, so {what} cannot be read. This is not a report that there are none."
        ),
    )


async def _read_investigation_reviews(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
) -> tuple[list[PendingDecision], SourceReading]:
    """Investigations under review that name this user as the reviewer."""
    label = "Investigations awaiting my review"
    tables = (InvestigationRun.__tablename__,)
    absent = await absent_tables(db, tables)
    if absent:
        return [], _unavailable(SOURCE_INVESTIGATION_REVIEW, label, absent, "investigations under review")

    stmt = (
        select(
            InvestigationRun.id,
            InvestigationRun.reference_number,
            InvestigationRun.title,
            InvestigationRun.updated_at,
        )
        .where(
            InvestigationRun.tenant_id == tenant_id,
            InvestigationRun.status == InvestigationStatus.UNDER_REVIEW,
            InvestigationRun.reviewer_user_id == user_id,
        )
        .order_by(InvestigationRun.updated_at.desc())
        .limit(MAX_ITEMS_PER_SOURCE + 1)
    )

    rows = (await db.execute(stmt)).all()
    truncated = len(rows) > MAX_ITEMS_PER_SOURCE

    items = [
        PendingDecision(
            key=f"{SOURCE_INVESTIGATION_REVIEW}:{row.id}",
            source=SOURCE_INVESTIGATION_REVIEW,
            source_label=label,
            decision="review",
            title=row.title,
            reference=row.reference_number,
            requested_at=row.updated_at,
            # The move into under_review is not timestamped anywhere on the row:
            # `reviewed_at` records the review finishing, and `completed_at` a
            # later state. "Last updated" is the closest true statement.
            requested_at_basis=BASIS_LAST_UPDATED,
            due_at=None,
            deep_link=f"/investigations/{row.id}",
        )
        for row in rows[:MAX_ITEMS_PER_SOURCE]
    ]

    return items, SourceReading(
        key=SOURCE_INVESTIGATION_REVIEW,
        label=label,
        status="live",
        count=len(items),
        truncated=truncated,
    )


async def _read_document_approvals(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
) -> tuple[list[PendingDecision], SourceReading]:
    """Controlled-document approvals whose current step names this user.

    The absent-table check comes first and is not an optimisation: on PostgreSQL a
    SELECT against a missing relation aborts the transaction, which would take the
    other sources in this request down with it.
    """
    label = "Controlled documents naming me as approver"
    tables = (
        DocumentApprovalInstance.__tablename__,
        DocumentApprovalWorkflow.__tablename__,
    )
    absent = await absent_tables(db, tables)
    if absent:
        return [], _unavailable(SOURCE_DOCUMENT_APPROVAL, label, absent, "document approvals")

    # Explicit columns: selecting whole entities here would load every document
    # column for a list that shows four fields.
    #
    # Not capped in SQL, because the cap applies to rows that survive attribution
    # and attribution needs the workflow JSON. The `status == pending` and tenant
    # filters bound the scan.
    stmt = (
        select(
            DocumentApprovalInstance.id,
            DocumentApprovalInstance.document_id,
            DocumentApprovalInstance.current_step,
            DocumentApprovalInstance.initiated_date,
            DocumentApprovalInstance.due_date,
            DocumentApprovalWorkflow.workflow_steps,
            ControlledDocument.document_number,
            ControlledDocument.title,
        )
        .join(
            DocumentApprovalWorkflow,
            DocumentApprovalWorkflow.id == DocumentApprovalInstance.workflow_id,
        )
        .join(
            ControlledDocument,
            ControlledDocument.id == DocumentApprovalInstance.document_id,
        )
        .where(
            DocumentApprovalInstance.tenant_id == tenant_id,
            DocumentApprovalWorkflow.tenant_id == tenant_id,
            ControlledDocument.tenant_id == tenant_id,
            DocumentApprovalInstance.status == "pending",
        )
        .order_by(DocumentApprovalInstance.initiated_date.desc())
    )

    rows = (await db.execute(stmt)).all()

    items: list[PendingDecision] = []
    unattributed = 0
    truncated = False
    for row in rows:
        approvers, attributable = approvers_for_step(row.workflow_steps, row.current_step)
        if not attributable:
            unattributed += 1
            continue
        if user_id not in approvers:
            continue
        if len(items) >= MAX_ITEMS_PER_SOURCE:
            truncated = True
            break
        items.append(
            PendingDecision(
                key=f"{SOURCE_DOCUMENT_APPROVAL}:{row.id}",
                source=SOURCE_DOCUMENT_APPROVAL,
                source_label=label,
                decision="approve",
                title=row.title,
                reference=row.document_number,
                requested_at=row.initiated_date,
                requested_at_basis=BASIS_SUBMITTED,
                due_at=row.due_date,
                # The Document Control register opens this record from the query
                # string; it is where the document and its approval state are read.
                deep_link=f"/document-control?document={row.document_id}",
            )
        )

    return items, SourceReading(
        key=SOURCE_DOCUMENT_APPROVAL,
        label=label,
        status="live",
        count=len(items),
        unattributed=unattributed,
        truncated=truncated,
    )


async def _read_signature_requests(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    user_email: Optional[str],
) -> tuple[list[PendingDecision], SourceReading]:
    """Signature requests where this user is a signer who has not yet signed.

    Matched on user id *or* email because ``SignatureRequestSigner`` supports
    signers who hold no account, and a user invited by address before their
    account existed still owes the signature.
    """
    label = "Signature requests awaiting my signature"
    tables = (
        SignatureRequest.__tablename__,
        SignatureRequestSigner.__tablename__,
    )
    absent = await absent_tables(db, tables)
    if absent:
        return [], _unavailable(SOURCE_SIGNATURE_REQUEST, label, absent, "outstanding signatures")

    me = [SignatureRequestSigner.user_id == user_id]
    if user_email:
        me.append(func.lower(SignatureRequestSigner.email) == user_email.strip().lower())

    # Tenant is filtered on the request; the signer row reaches this tenant only
    # through that join, and its own tenant_id is nullable.
    #
    # distinct(): a user can appear on one request as both an account and an
    # address, and one request is one decision.
    stmt = (
        select(
            SignatureRequest.id,
            SignatureRequest.reference_number,
            SignatureRequest.title,
            SignatureRequest.created_at,
            SignatureRequest.expires_at,
        )
        .join(SignatureRequestSigner, SignatureRequestSigner.request_id == SignatureRequest.id)
        .where(
            SignatureRequest.tenant_id == tenant_id,
            SignatureRequest.status.in_(_SIGNATURE_REQUEST_OPEN_STATUSES),
            SignatureRequestSigner.status.in_(_SIGNATURE_SIGNER_OPEN_STATUSES),
            or_(*me),
        )
        .distinct()
        .order_by(SignatureRequest.created_at.desc())
        .limit(MAX_ITEMS_PER_SOURCE + 1)
    )

    rows = (await db.execute(stmt)).all()
    truncated = len(rows) > MAX_ITEMS_PER_SOURCE

    items = [
        PendingDecision(
            key=f"{SOURCE_SIGNATURE_REQUEST}:{row.id}",
            source=SOURCE_SIGNATURE_REQUEST,
            source_label=label,
            decision="sign",
            title=row.title,
            reference=row.reference_number,
            requested_at=row.created_at,
            requested_at_basis=BASIS_RAISED,
            due_at=row.expires_at,
            # No route. `/signatures` renders a hardcoded empty list and never
            # calls the signatures API (frontend/src/pages/DigitalSignatures.tsx),
            # so linking there would send a user holding real work to a screen
            # that tells them they have none.
            deep_link=None,
        )
        for row in rows[:MAX_ITEMS_PER_SOURCE]
    ]

    return items, SourceReading(
        key=SOURCE_SIGNATURE_REQUEST,
        label=label,
        status="live",
        count=len(items),
        truncated=truncated,
    )


def _sort_key(item: PendingDecision) -> tuple[int, float, str]:
    """Soonest due first, undated last, then newest request, then a stable tiebreak.

    Undated items sort last rather than first: a decision with no deadline is not
    urgent, and putting it above a dated one would push real deadlines off the
    top of a short panel.
    """
    if item.due_at is not None:
        return (0, item.due_at.timestamp(), item.key)
    requested = item.requested_at.timestamp() if item.requested_at else 0.0
    return (1, -requested, item.key)


async def collect_my_decisions(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    user_email: Optional[str] = None,
) -> MyDecisions:
    """Ask every wired domain what this user owes, and account for the ones that could not answer.

    Sources are read in sequence rather than gathered concurrently: they share one
    ``AsyncSession``, which is not safe for concurrent use, and a session per
    source would buy latency at the cost of reading the request in several
    transactions.
    """
    items: list[PendingDecision] = []
    sources: list[SourceReading] = []

    investigation_items, investigation_reading = await _read_investigation_reviews(
        db, tenant_id=tenant_id, user_id=user_id
    )
    items.extend(investigation_items)
    sources.append(investigation_reading)

    document_items, document_reading = await _read_document_approvals(db, tenant_id=tenant_id, user_id=user_id)
    items.extend(document_items)
    sources.append(document_reading)

    signature_items, signature_reading = await _read_signature_requests(
        db, tenant_id=tenant_id, user_id=user_id, user_email=user_email
    )
    items.extend(signature_items)
    sources.append(signature_reading)

    return MyDecisions(items=tuple(sorted(items, key=_sort_key)), sources=tuple(sources))
