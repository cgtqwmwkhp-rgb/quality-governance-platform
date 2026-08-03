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
