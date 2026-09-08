"""Request/response contracts for ICAM contributing factors (INV-C12 / DEC-1).

A separate module from ``investigation_rca.py`` so the factors surface can be
read in one place, and because the RCA schemas are shared with the 5-Whys and
CAPA-per-Why work already shipped.

The taxonomy is not invented here. ``category`` is
:class:`~src.domain.models.rca_tools.FishboneCategory`, re-specified to the four
ICAM categories, and ``depth`` is
:class:`~src.domain.models.rca_tools.CausalDepth`, the HSG245 causal depth. Both
are enums on the wire, so a misspelled category is a 422 rather than a factor
filed under a category nothing will ever read back.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.models.rca_tools import CausalDepth, FishboneCategory
from src.domain.services.investigation_factors_service import FACTOR_SUB_CAUSES_MAX, FACTOR_TEXT_MAX_LENGTH


def _required_text(value: str) -> str:
    """Reject text that is only whitespace, and store what was typed, trimmed.

    ``min_length=1`` alone would accept ``"   "`` and the service would store a
    factor with no words in it. The brief for this surface is that empty factor
    text is refused, not invented, so the refusal happens at the schema and the
    client gets a 422 naming the field.
    """
    text = value.strip()
    if not text:
        raise ValueError("must not be empty")
    return text


def _clean_sub_causes(values: List[str]) -> List[str]:
    """Trim sub-causes and drop the blank ones, keeping the order given.

    A blank row in the editor is "no sub-cause here", not a sub-cause with no
    text; dropping it stores what the investigator meant without inventing
    anything. A sub-cause that is only whitespace therefore disappears rather
    than 422-ing the whole factor, because the factor itself is still valid.
    """
    cleaned = [str(value).strip() for value in values]
    return [value for value in cleaned if value]


class InvestigationFactorResponse(BaseModel):
    """One contributing factor.

    ``depth`` is nullable because a cause written through the generic
    ``/rca-tools/fishbone`` routes before INV-C12 has no recorded depth. Null
    means nobody stated one — it is never filled in with a guess.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    investigation_id: int
    category: FishboneCategory
    cause: str
    sub_causes: List[str]
    depth: Optional[CausalDepth] = None


class InvestigationFactorListResponse(BaseModel):
    """The run's contributing factors, in ICAM category order.

    ``items: []`` is a valid, successful answer — a run with no factors is a
    normal state, not an error, and the editor renders it as an empty list with
    a picker rather than as a failure.

    ``contributing_factors_text`` is the paragraph derived from these factors
    and written back to ``investigation_runs.data`` (and to the run's 5-Whys
    analysis when it has one). It is returned so a caller can see exactly what
    the closure gate and the generated pack will read, without re-deriving it
    and risking deriving it differently.

    ``unmapped_categories`` and ``unreadable_total`` are the honest count of
    stored causes this surface does **not** present: a diagram keyed by the old
    manufacturing 6M names, an entry that is not an object, or one with no
    text. They are left in the JSON untouched — reporting them is how a client
    can tell "this run has no factors" apart from "this run has factors this
    screen cannot show you".
    """

    items: List[InvestigationFactorResponse]
    total: int
    investigation_id: int
    diagram_id: Optional[int] = None
    contributing_factors_text: str
    unmapped_categories: List[str] = Field(default_factory=list)
    unreadable_total: int = 0


class InvestigationFactorCreate(BaseModel):
    """Add one contributing factor under one ICAM category.

    ``depth`` is required rather than defaulted. ICAM crossed with HSG245 depth
    is the whole of DEC-1; a factor stored with a depth the server chose would
    be the platform asserting how far back a cause sits, which is the
    investigator's judgement and nobody else's.
    """

    model_config = ConfigDict(extra="forbid")

    category: FishboneCategory
    cause: str = Field(..., min_length=1, max_length=FACTOR_TEXT_MAX_LENGTH)
    sub_causes: List[str] = Field(default_factory=list, max_length=FACTOR_SUB_CAUSES_MAX)
    depth: CausalDepth

    @field_validator("cause")
    @classmethod
    def _cause_is_not_blank(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("sub_causes")
    @classmethod
    def _sub_causes_are_text(cls, value: List[str]) -> List[str]:
        cleaned = _clean_sub_causes(value)
        for item in cleaned:
            if len(item) > FACTOR_TEXT_MAX_LENGTH:
                raise ValueError(f"each sub-cause must be at most {FACTOR_TEXT_MAX_LENGTH} characters")
        return cleaned


class InvestigationFactorUpdate(BaseModel):
    """Change one contributing factor.

    Every field is optional and every field left out is left alone, so an edit
    to the wording cannot blank a depth the client never mentioned. Sending
    ``"depth": null`` explicitly *does* clear it — "not mentioned" and "stated
    to be unknown" are different answers, and Pydantic's ``model_fields_set``
    is what tells them apart.

    A body with no fields at all is refused rather than answered with a
    successful no-op, because the plausible cause is a client that meant to
    send something.

    ``category`` moves the factor to another ICAM category and keeps its id: it
    is the same factor, re-classified.
    """

    model_config = ConfigDict(extra="forbid")

    category: Optional[FishboneCategory] = None
    cause: Optional[str] = Field(default=None, min_length=1, max_length=FACTOR_TEXT_MAX_LENGTH)
    sub_causes: Optional[List[str]] = Field(default=None, max_length=FACTOR_SUB_CAUSES_MAX)
    depth: Optional[CausalDepth] = None

    @field_validator("cause")
    @classmethod
    def _cause_is_not_blank(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _required_text(value)

    @field_validator("sub_causes")
    @classmethod
    def _sub_causes_are_text(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        cleaned = _clean_sub_causes(value)
        for item in cleaned:
            if len(item) > FACTOR_TEXT_MAX_LENGTH:
                raise ValueError(f"each sub-cause must be at most {FACTOR_TEXT_MAX_LENGTH} characters")
        return cleaned

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "InvestigationFactorUpdate":
        if not self.model_fields_set:
            raise ValueError("name at least one field to change")
        return self

    @property
    def clears_depth(self) -> bool:
        """True when the caller explicitly sent ``depth: null``."""
        return "depth" in self.model_fields_set and self.depth is None
