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

The session factory arrives as an argument rather than as an import, for the same
reason the kill-switch modules take one: ``src/domain`` may not import
``src/infrastructure``, and ``scripts/check_import_boundaries.py`` enforces it.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import AsyncContextManager, Awaitable, Callable, Dict, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings as global_settings
from src.domain.features.catalogue import CLIENT_FEATURES, ClientFeature
from src.domain.models.feature_flag import FeatureFlag
from src.domain.models.user import User

logger = logging.getLogger(__name__)

SUCCESS_TTL_SECONDS = 30.0
ERROR_RETRY_SECONDS = 5.0

SessionFactory = Callable[[], AsyncContextManager[AsyncSession]]


def _kill_switch_readers(session_factory: SessionFactory) -> Mapping[str, Callable[[], Awaitable[bool]]]:
    """Map a kill-switch flag key to the cached reader the feature's own routes use."""
    from src.domain.services.compliance_schedule_kill_switch import compliance_schedule_kill_switch_engaged
    from src.domain.services.copilot_kill_switch import copilot_kill_switch_engaged

    return {
        "compliance_schedule_kill_switch": lambda: compliance_schedule_kill_switch_engaged(session_factory),
        "copilot_kill_switch": lambda: copilot_kill_switch_engaged(session_factory),
    }


def _unusable_session_factory() -> AsyncContextManager[AsyncSession]:
    raise RuntimeError("session factory requested while only enumerating kill-switch keys")


def kill_switch_reader_keys() -> frozenset[str]:
    """Keys this module knows how to read, without needing a real session factory.

    Derived from the one map rather than restated, so the drift test cannot pass
    against a list that has fallen out of step with the readers it describes. The
    readers are never invoked here, so the sentinel factory is never called.
    """
    return frozenset(_kill_switch_readers(_unusable_session_factory))


@dataclass(frozen=True)
class _Verdict:
    enabled: bool
    asked_at: float
    expires_at: float


_enabling_flag_cache: Dict[str, _Verdict] = {}


def reset_client_feature_cache() -> None:
    """Forget every cached enabling-flag verdict. For tests, and for a forced re-read."""
    _enabling_flag_cache.clear()


async def _enabling_flag_open(key: str, session_factory: SessionFactory) -> bool:
    """Whether a positive ``feature_flags`` row leaves the feature open.

    Absent row means open, matching ``_ensure_user_management_enabled``.
    """
    asked_at = time.monotonic()
    cached = _enabling_flag_cache.get(key)
    if cached is not None and asked_at < cached.expires_at:
        return cached.enabled

    try:
        async with session_factory() as session:
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


async def _feature_enabled(
    feature: ClientFeature,
    user: Optional[User],
    session_factory: SessionFactory,
) -> bool:
    if feature.settings_attr is not None and not bool(getattr(global_settings, feature.settings_attr, False)):
        return False

    if feature.kill_switch_key is not None:
        reader = _kill_switch_readers(session_factory).get(feature.kill_switch_key)
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

    if feature.enabling_flag_key is not None and not await _enabling_flag_open(
        feature.enabling_flag_key, session_factory
    ):
        return False

    if feature.required_permission is not None:
        if user is None or not user.has_permission(feature.required_permission):
            return False

    return True


async def evaluate_client_features(user: Optional[User], session_factory: SessionFactory) -> Dict[str, bool]:
    """Effective value of every registered client feature for this caller."""
    return {feature.ui_key: await _feature_enabled(feature, user, session_factory) for feature in CLIENT_FEATURES}


__all__ = [
    "SUCCESS_TTL_SECONDS",
    "SessionFactory",
    "evaluate_client_features",
    "kill_switch_reader_keys",
    "reset_client_feature_cache",
]
