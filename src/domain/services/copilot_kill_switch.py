"""Runtime kill switch for the AI Copilot surface (PX-248 follow-up).

``AI_COPILOT_ENABLED`` is process configuration: turning the copilot off in a
running environment costs a redeploy. This module adds a second gate that an
operator can pull from the database, so a copilot that starts saying something
it should not can be closed in the time it takes to run one UPDATE.

Subtract-only
-------------
The switch can close the surface and can never open it. That is enforced twice,
deliberately:

* *By meaning.* The flag row records whether the **kill** is engaged, not
  whether the copilot is allowed. ``enabled=True`` means "kill it". So there is
  no value of the row that grants anything.
* *By call order.* Callers check ``settings.ai_copilot_enabled`` first and only
  consult this module when it is already ``True`` — see
  :func:`src.domain.services.copilot_service.copilot_is_enabled`. A copilot that
  configuration has not opened never reaches a database read at all.

Either one alone would be sufficient. Both are present because "the DB can turn
production AI on" is the failure this module must not have.

Why this does not use :class:`~src.domain.services.feature_flag_service.FeatureFlagService`
-------------------------------------------------------------------------------------------
That service memoises flag rows in a module-level dict with no expiry, and only
its own ``update_flag`` writes to that dict. A kill engaged by SQL, or by any
other worker process, would therefore never be observed by a process that had
already read the row once. A kill switch that can be silently stale is not a
kill switch, so the read here is a direct, short-TTL query instead.

It also reads only ``enabled`` and ignores ``rollout_percentage`` and
``tenant_overrides``. A partially-applied kill is not a thing anyone wants at
2am; see :data:`KILL_SWITCH_FLAG_KEY` for the per-tenant limitation.
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

#: Row in ``feature_flags`` that engages the kill. ``enabled=True`` closes the
#: copilot; ``enabled=False`` or no row at all leaves configuration in charge.
#:
#: Global rather than per-tenant. The HTTP guard runs ahead of authentication so
#: that a disabled copilot is indistinguishable from one that was never built,
#: and at that point there is no tenant to scope to. Per-tenant suppression would
#: have to move the check after authentication and give up that property.
KILL_SWITCH_FLAG_KEY = "copilot_kill_switch"

#: How long a successful read is trusted. Bounds both the database load (one
#: query per process per interval, not per request) and how long a newly engaged
#: kill can take to reach a running process.
SUCCESS_TTL_SECONDS = 30.0

#: Backoff after a failed read, so an unreachable database is not re-queried on
#: every request. Shorter than the success TTL: not knowing is worse than knowing.
ERROR_RETRY_SECONDS = 5.0

#: A session factory, not a session. The read must never run on a caller's
#: session: a failing statement leaves that session in a rolled-back-pending
#: state, so a missing ``feature_flags`` table would turn "the kill switch could
#: not be read" into "the request the caller was actually making now fails".
SessionFactory = Callable[[], AsyncContextManager[AsyncSession]]


@dataclass(frozen=True)
class _Verdict:
    engaged: bool
    #: Monotonic time at which the read that produced this *started*. Used to
    #: resolve concurrent refreshes in favour of the one that asked most
    #: recently, rather than the one that happened to finish last.
    asked_at: float
    expires_at: float


_verdict: Optional[_Verdict] = None


def reset_copilot_kill_switch_cache() -> None:
    """Forget any cached verdict. For tests, and for a process that wants a re-read."""
    global _verdict
    _verdict = None


def copilot_kill_switch_last_known() -> bool:
    """The last observed verdict, without doing any I/O.

    For callers that have no session factory to hand. This is weaker than
    :func:`copilot_kill_switch_engaged`: a process that has never completed a
    read reports ``False``, because "not yet observed" cannot be distinguished
    from "not engaged" without asking. Use it only as a second line behind a
    caller that does refresh.
    """
    verdict = _verdict
    return verdict.engaged if verdict is not None else False


async def copilot_kill_switch_engaged(session_factory: SessionFactory) -> bool:
    """Whether an operator has closed the copilot. Refreshes at most once per TTL.

    Never raises. A read that fails is reported below, and the surface stays in
    whatever state was last observed.
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
    """Decide what an unreadable switch means, and remember it briefly.

    A kill already observed stays engaged: an infrastructure failure must not be
    able to reopen a surface an operator deliberately closed, so only a
    successful read saying otherwise can clear it.

    A kill never observed is treated as not engaged. This is the one place the
    module is not fail-closed, and the reason is that the copilot is only open
    at all because ``AI_COPILOT_ENABLED`` was explicitly set: falling back to
    "configuration decides" returns to the previously accepted posture rather
    than to a worse one, whereas failing closed would take the feature down on
    any database wobble.
    """
    stuck = cached is not None and cached.engaged
    logger.warning(
        "AI Copilot kill switch could not be read (%s); treating as %s",
        type(exc).__name__,
        "engaged, as last observed" if stuck else "not engaged",
    )
    _store(_Verdict(engaged=stuck, asked_at=asked_at, expires_at=asked_at + ERROR_RETRY_SECONDS))
    return stuck


def _store(verdict: _Verdict) -> None:
    """Publish a verdict unless a more recently *started* read already has."""
    global _verdict
    current = _verdict
    if current is not None and current.asked_at > verdict.asked_at:
        return
    _verdict = verdict


async def _read_kill_switch(session_factory: SessionFactory) -> bool:
    """Read the flag on a session of our own.

    Selects the column rather than the entity on purpose: no ORM instance means
    nothing that can be handed back later, detached and stale, the way
    ``FeatureFlagService``'s cache does.
    """
    async with session_factory() as session:
        result = await session.execute(select(FeatureFlag.enabled).where(FeatureFlag.key == KILL_SWITCH_FLAG_KEY))
        enabled = result.scalar_one_or_none()
    # No row is the shipped state and means nobody has engaged the kill.
    return bool(enabled)
