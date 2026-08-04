"""Pydantic schemas for the client feature-flag channel.

Named ``ClientFeatureFlags*`` rather than ``FeatureFlag*`` because
:mod:`src.api.schemas.feature_flag` already owns the latter for the DB-backed
admin API, and the two would collide as OpenAPI component names.
"""

from datetime import datetime
from typing import Dict, Literal

from pydantic import BaseModel, Field


class ClientFeatureFlagsResponse(BaseModel):
    """The set of UI features this deployment is prepared to show the caller."""

    flags: Dict[str, bool] = Field(
        ...,
        description=(
            "Effective value per feature key: the configuration opener, the kill switch "
            "and the caller's permission folded into a single boolean."
        ),
    )
    scope: Literal["anonymous", "user"] = Field(
        ...,
        description=(
            "Whether a caller identity was presented. Permission-gated features are always "
            "false for 'anonymous', so a client must refetch after signing in."
        ),
    )
    evaluated_at: datetime = Field(..., description="When the server evaluated these flags (UTC).")
    ttl_seconds: int = Field(
        ...,
        description=(
            "How long the client may treat this response as fresh. Advisory: the response "
            "is sent no-store because it varies per caller."
        ),
    )
