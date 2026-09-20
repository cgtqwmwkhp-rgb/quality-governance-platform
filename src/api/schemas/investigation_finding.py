"""Request/response contracts for investigation findings rows (INV-C7).

A separate module from ``investigation.py`` so the findings surface can be read in
one place, and because the run schemas are shared with the timeline and closure
work in flight.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.domain.models.investigation_finding import FINDING_BODY_MAX_LENGTH


class InvestigationFindingResponse(BaseModel):
    """One finding row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    investigation_id: int
    body: str
    sort_order: int
    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InvestigationFindingListResponse(BaseModel):
    """The run's findings, in order.

    ``items: []`` is a valid, successful answer — a run with no findings is a
    normal state, not an error, and the editor renders it as an empty list with an
    add button rather than as a failure.

    ``findings_text`` is the concatenation stored back into
    ``investigation_runs.data``. It is returned so a caller can see exactly what
    the closure gate and the generated pack will read, without having to re-derive
    it and risk deriving it differently.
    """

    items: List[InvestigationFindingResponse]
    total: int
    investigation_id: int
    findings_text: str


class InvestigationFindingCreate(BaseModel):
    """Add one finding to the end of the list."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(..., min_length=1, max_length=FINDING_BODY_MAX_LENGTH)


class InvestigationFindingUpdate(BaseModel):
    """Rewrite one finding's text.

    Only the text is editable here. Position is moved by the reorder endpoint, so
    a text edit cannot reshuffle the list as a side effect.
    """

    model_config = ConfigDict(extra="forbid")

    body: str = Field(..., min_length=1, max_length=FINDING_BODY_MAX_LENGTH)


class InvestigationFindingReorderRequest(BaseModel):
    """The complete list of this run's finding ids, in the order wanted.

    Complete on purpose: a partial list is refused rather than applied, so a stale
    editor cannot drop a finding another tab has just added by omitting its id.
    """

    model_config = ConfigDict(extra="forbid")

    finding_ids: List[int] = Field(..., min_length=1)
