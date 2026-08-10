"""Read-only aggregate of the decisions outstanding for the caller.

One endpoint, ``GET /api/v1/approvals/my-decisions``. It owns no table and writes
nothing: recording a decision stays with the domain that raised it, so that the
audit trail lives next to the record rather than in a second place that has to be
reconciled with it. For controlled documents that is
``POST /api/v1/document-control/approvals/{instance_id}/action``; for
investigations, ``POST /api/v1/investigations/{id}/approve``.

The response deliberately reports the state of every source it asked, not just the
items it found — see ``src/domain/services/approvals_read_model.py`` for why an
empty list from this endpoint is not by itself a statement that the caller is
clear.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.dependencies import DbSession, require_permission
from src.api.utils.tenant import require_tenant_id
from src.domain.models.user import User
from src.domain.services.approvals_read_model import collect_my_decisions

router = APIRouter()


class PendingDecisionResponse(BaseModel):
    """One outstanding decision, as the owning domain reported it."""

    key: str = Field(description="`{source}:{id}`. Stable within a source; not an id on its own.")
    source: str
    source_label: str
    decision: str = Field(description="The verb the owning domain uses, e.g. `approve`, `review`, `sign`.")
    title: str
    reference: Optional[str] = None
    requested_at: Optional[datetime] = None
    requested_at_basis: Optional[str] = Field(
        default=None,
        description=(
            "What `requested_at` is a record of: `submitted` (approval was requested "
            "then), `raised` (the request was created then) or `last_updated` (the "
            "domain does not timestamp the transition, so this is the last change to "
            "the record). Render the date with this qualifier rather than as a "
            "request time."
        ),
    )
    due_at: Optional[datetime] = None
    deep_link: Optional[str] = Field(
        default=None,
        description=(
            "Route to the screen that owns the record, or null when this product has no "
            "screen that reads it. Null must be rendered as 'no screen yet', never "
            "substituted with a guessed route."
        ),
    )


class DecisionSourceResponse(BaseModel):
    """Whether a domain could be asked, and what it said."""

    key: str
    label: str
    status: str = Field(description="`live` (read; `count` is a measurement) or `unavailable`.")
    count: Optional[int] = Field(
        default=None,
        description="Null when `status` is `unavailable`. Zero only ever means zero.",
    )
    reason: Optional[str] = None
    unattributed: int = Field(
        default=0,
        description=(
            "Rows this source holds that name nobody — an approval step with no approvers, "
            "a review with no reviewer — so they are outstanding for no one and appear in "
            "no user's queue."
        ),
    )
    truncated: bool = Field(
        default=False,
        description="True when a per-source cap cut the list, making `count` a floor for this source.",
    )


class MyDecisionsResponse(BaseModel):
    """Decisions attributed to the caller, plus the state of every source asked."""

    items: list[PendingDecisionResponse]
    total: int = Field(
        description=("Rows in `items`. A floor rather than a total whenever `sources_complete` is false.")
    )
    sources_complete: bool = Field(
        description=(
            "False when at least one source could not be read. An empty `items` with this "
            "false is NOT a report that nothing is outstanding."
        )
    )
    unavailable_sources: list[str] = Field(
        default_factory=list,
        description="Source keys that could not be read, e.g. ['document_approval'].",
    )
    sources: list[DecisionSourceResponse]


@router.get("/my-decisions", response_model=MyDecisionsResponse)
async def list_my_decisions(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("action:read"))],
) -> MyDecisionsResponse:
    """Decisions waiting on the caller, gathered from the domains that hold them.

    Requires `action:read` — the same permission as the personal work queue this
    panel sits beside. It is not gated on the permissions of the underlying
    domains, because every row returned is one the caller is named on, and a user
    who cannot see their own outstanding approval cannot act on it.

    Read `sources_complete` before rendering: `items: []` with
    `sources_complete: false` means at least one domain could not be read, which
    is not the same answer as "you have nothing".
    """
    tenant_id = require_tenant_id(current_user.tenant_id)

    decisions = await collect_my_decisions(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        user_email=current_user.email,
    )

    return MyDecisionsResponse(
        items=[
            PendingDecisionResponse(
                key=item.key,
                source=item.source,
                source_label=item.source_label,
                decision=item.decision,
                title=item.title,
                reference=item.reference,
                requested_at=item.requested_at,
                requested_at_basis=item.requested_at_basis,
                due_at=item.due_at,
                deep_link=item.deep_link,
            )
            for item in decisions.items
        ],
        total=decisions.total,
        sources_complete=decisions.sources_complete,
        unavailable_sources=list(decisions.unavailable_sources),
        sources=[
            DecisionSourceResponse(
                key=source.key,
                label=source.label,
                status=source.status,
                count=source.count,
                reason=source.reason,
                unattributed=source.unattributed,
                truncated=source.truncated,
            )
            for source in decisions.sources
        ],
    )
