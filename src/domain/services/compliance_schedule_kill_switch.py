"""Runtime kill switch for Compliance Schedule (Wave 0).

Copied from :mod:`src.domain.services.copilot_kill_switch` so the same subtract-only
properties hold: ``enabled=True`` means *kill*, configuration
(``settings.compliance_schedule_enabled``) is checked first by callers, and the
read bypasses :class:`~src.domain.services.feature_flag_service.FeatureFlagService`
because that service's process-local cache has no TTL.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import AsyncContextManager, Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.domain.models.feature_flag import FeatureFlag

logger = logging.getLogger(__name__)

KILL_SWITCH_FLAG_KEY = "compliance_schedule_kill_switch"

SUCCESS_TTL_SECONDS = 30.0
ERROR_RETRY_SECONDS = 5.0

SessionFactory = Callable[[], AsyncContextManager[AsyncSession]]


@dataclass(frozen=True)
class _Verdict:
    engaged: bool
    asked_at: float
    expires_at: float


_verdict: Optional[_Verdict] = None


def reset_compliance_schedule_kill_switch_cache() -> None:
    """Forget any cached verdict. For tests, and for a process that wants a re-read."""
    global _verdict
    _verdict = None


def compliance_schedule_kill_switch_last_known() -> bool:
    """The last observed verdict, without doing any I/O."""
    verdict = _verdict
    return verdict.engaged if verdict is not None else False


async def compliance_schedule_is_open(session_factory: SessionFactory) -> bool:
    """Whether Compliance Schedule is available: configuration opener, then kill switch.

    Lives here rather than at a call site because the two inputs read in opposite
    directions -- ``compliance_schedule_enabled`` is permissive, the kill switch is
    ``True`` for *closed*. Every caller that composes them itself is a chance to
    negate the wrong one, so the composition exists once and callers ask this.

    The opener is checked first because it costs nothing and a disabled module must
    not issue a query per call.
    """
    if not settings.compliance_schedule_enabled:
        return False
    return not await compliance_schedule_kill_switch_engaged(session_factory)


def compliance_schedule_is_open_last_known() -> bool:
    """``compliance_schedule_is_open`` for callers that must not perform I/O.

    Same composition and the same direction of each input, but it reads the cached
    kill verdict instead of refreshing it, so it never opens a session. That matters
    for a caller running on someone else's transaction: a failed read there would
    leave that session unusable for the caller's own work. This is the posture
    ``copilot_service.send_message`` already takes with its own switch.

    The cost is that a process which has never refreshed the verdict sees no kill.
    That is the subtract-only direction failing safe-for-availability, not
    safe-for-closure, and it is why the configuration opener is checked first and
    is the gate that must be relied on: ``compliance_schedule_enabled`` is read from
    configuration on every call and cannot be stale.
    """
    if not settings.compliance_schedule_enabled:
        return False
    return not compliance_schedule_kill_switch_last_known()


async def compliance_schedule_kill_switch_engaged(session_factory: SessionFactory) -> bool:
    """Whether an operator has closed Compliance Schedule. Refreshes at most once per TTL.

    Never raises. A read that fails leaves an already-observed kill engaged.
    """
    asked_at = time.monotonic()
    cached = _verdict
    if cached is not None and asked_at < cached.expires_at:
        return cached.engaged

    try:
        engaged = await _read_kill_switch(session_factory)
    except Exception as exc:  # noqa: BLE001 - an unreadable switch must not break the request
        return _record_failed_read(cached, asked_at, exc)

    _store(_Verdict(engaged=engaged, asked_at=asked_at, expires_at=asked_at + SUCCESS_TTL_SECONDS))
    return engaged


def _record_failed_read(cached: Optional[_Verdict], asked_at: float, exc: Exception) -> bool:
    stuck = cached is not None and cached.engaged
    logger.warning(
        "Compliance Schedule kill switch could not be read (%s); treating as %s",
        type(exc).__name__,
        "engaged, as last observed" if stuck else "not engaged",
    )
    _store(_Verdict(engaged=stuck, asked_at=asked_at, expires_at=asked_at + ERROR_RETRY_SECONDS))
    return stuck


def _store(verdict: _Verdict) -> None:
    global _verdict
    current = _verdict
    if current is not None and current.asked_at > verdict.asked_at:
        return
    _verdict = verdict


async def _read_kill_switch(session_factory: SessionFactory) -> bool:
    async with session_factory() as session:
        result = await session.execute(select(FeatureFlag.enabled).where(FeatureFlag.key == KILL_SWITCH_FLAG_KEY))
        enabled = result.scalar_one_or_none()
    return bool(enabled)
