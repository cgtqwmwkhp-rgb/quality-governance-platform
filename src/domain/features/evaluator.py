"""Evaluate :data:`~src.domain.features.catalogue.CLIENT_FEATURES` for one caller.

The point of this module is that the answer it gives a browser is the *same*
answer the API itself acts on. Kill-switch verdicts are therefore not re-derived
here: they dispatch to the very functions the feature routers call in their own
404 gates, so within a process the nav and the endpoint cannot disagree, and the
already-cached verdict means the common case costs no database round trip.

Positive enabling flags have no such existing reader, so this module supplies one
with the same 30-second TTL the kill switches use. It never raises: a database
that cannot be read leaves the previously observed value in place, and an
unreadable flag that has never been read is treated as *enabled*, matching
``_ensure_user_management_enabled``'s behaviour of allowing through when the
lookup fails.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Mapping, Optional

from sqlalchemy import select

from src.core.config import settings as global_settings
from src.domain.features.catalogue import CLIENT_FEATURES, ClientFeature
from src.domain.models.feature_flag import FeatureFlag
from src.domain.models.user import User

logger = logging.getLogger(__name__)

SUCCESS_TTL_SECONDS = 30.0
ERROR_RETRY_SECONDS = 5.0


def _kill_switch_readers() -> Mapping[str, Callable[[], Awaitable[bool]]]:
    """Map a kill-switch flag key to the cached reader the feature's own routes use.

    Imported lazily so this module stays importable without pulling the database
    session factory in at import time.
    """
    from src.domain.services.compliance_schedule_kill_switch import compliance_schedule_kill_switch_engaged
    from src.domain.services.copilot_kill_switch import copilot_kill_switch_engaged
    from src.infrastructure.database import async_session_maker

    return {
        "compliance_schedule_kill_switch": lambda: compliance_schedule_kill_switch_engaged(async_session_maker),
        "copilot_kill_switch": lambda: copilot_kill_switch_engaged(async_session_maker),
    }


@dataclass(frozen=True)
class _Verdict:
    enabled: bool
    asked_at: float
    expires_at: float


_enabling_flag_cache: Dict[str, _Verdict] = {}


def reset_client_feature_cache() -> None:
    """Forget every cached enabling-flag verdict. For tests, and for a forced re-read."""
    _enabling_flag_cache.clear()


async def _enabling_flag_open(key: str) -> bool:
    """Whether a positive ``feature_flags`` row leaves the feature open.

    Absent row means open, matching ``_ensure_user_management_enabled``.
    """
    asked_at = time.monotonic()
    cached = _enabling_flag_cache.get(key)
    if cached is not None and asked_at < cached.expires_at:
        return cached.enabled

    from src.infrastructure.database import async_session_maker

    try:
        async with async_session_maker() as session:
            result = await session.execute(select(FeatureFlag.enabled).where(FeatureFlag.key == key))
            row = result.scalar_one_or_none()
        enabled = True if row is None else bool(row)
    except Exception as exc:  # noqa: BLE001 - an unreadable flag must not break the request
        previous = cached.enabled if cached is not None else True
        logger.warning(
            "Client feature flag %s could not be read (%s); treating as %s",
            key,
            type(exc).__name__,
            "enabled" if previous else "disabled",
        )
        _enabling_flag_cache[key] = _Verdict(previous, asked_at, asked_at + ERROR_RETRY_SECONDS)
        return previous

    _enabling_flag_cache[key] = _Verdict(enabled, asked_at, asked_at + SUCCESS_TTL_SECONDS)
    return enabled


async def _feature_enabled(feature: ClientFeature, user: Optional[User]) -> bool:
    if feature.settings_attr is not None and not bool(getattr(global_settings, feature.settings_attr, False)):
        return False

    if feature.kill_switch_key is not None:
        reader = _kill_switch_readers().get(feature.kill_switch_key)
        if reader is None:
            # A registry entry naming a switch nothing can read is a wiring error.
            # Report the feature closed rather than silently ignoring the switch.
            logger.error(
                "No kill-switch reader registered for %s (feature %s); reporting closed",
                feature.kill_switch_key,
                feature.ui_key,
            )
            return False
        if await reader():
            return False

    if feature.enabling_flag_key is not None and not await _enabling_flag_open(feature.enabling_flag_key):
        return False

    if feature.required_permission is not None:
        if user is None or not user.has_permission(feature.required_permission):
            return False

    return True


async def evaluate_client_features(user: Optional[User]) -> Dict[str, bool]:
    """Effective value of every registered client feature for this caller."""
    return {feature.ui_key: await _feature_enabled(feature, user) for feature in CLIENT_FEATURES}


__all__ = [
    "SUCCESS_TTL_SECONDS",
    "evaluate_client_features",
    "reset_client_feature_cache",
]
