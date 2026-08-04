"""Client-facing metadata: which UI features this deployment has switched on.

This is the channel the frontend uses instead of guessing. It exists because a
statically built single-page app cannot know, at build time, which environment it
will be served to — and because baking the answer in would make the kill switch a
half-control, able to close the API but not to stop the UI advertising it.

Authentication is optional on purpose. The nav is only drawn after sign-in, so an
authenticated endpoint would nearly do; but permission-gated features must be
folded server-side (permissions are not in the JWT, so a browser cannot evaluate
them), and an endpoint that can 401 would make the very first call of a session a
race with token refresh. Answering anonymously with every permission-gated feature
reported false is simpler and strictly safer.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from src.api.dependencies import OptionalCurrentUser
from src.api.schemas.client_features import ClientFeatureFlagsResponse
from src.domain.features.evaluator import SUCCESS_TTL_SECONDS, evaluate_client_features

router = APIRouter(tags=["Meta"])


@router.get("/features", response_model=ClientFeatureFlagsResponse)
async def get_client_features(current_user: OptionalCurrentUser) -> ClientFeatureFlagsResponse:
    """Report the effective state of every client-facing feature flag.

    Each value folds together the configuration opener, the kill switch and the
    caller's permission, so a ``true`` means the caller can actually use the
    feature rather than merely that it exists in this build.
    """
    flags = await evaluate_client_features(current_user)
    return ClientFeatureFlagsResponse(
        flags=flags,
        scope="user" if current_user is not None else "anonymous",
        evaluated_at=datetime.now(timezone.utc),
        ttl_seconds=int(SUCCESS_TTL_SECONDS),
    )
