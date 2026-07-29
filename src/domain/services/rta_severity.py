"""Derive RTA injury flags and injury-outcome severity from reported evidence only.

Portal intake carries a generic triage word (low/medium/high/critical) shared by
incident/near-miss/complaint/RTA reporting. That word measures urgency, not human
harm, so it must never select a value on :class:`RTASeverity`, which is an
injury-outcome scale. Mapping one onto the other manufactures clinical claims:
"the van cannot be driven" became "a person died".
"""

from __future__ import annotations

from typing import Any, Optional

from src.domain.models.rta import RTASeverity

_TRUTHY_ANSWERS = frozenset({"yes", "y", "true", "t", "1", "injured"})
_FALSY_ANSWERS = frozenset({"no", "n", "false", "f", "0", "none"})


def interpret_rta_injury_answer(value: Any) -> Optional[bool]:
    """Read an RTA injury answer as True / False / unknown.

    Returns ``None`` when intake was never given an answer, so callers can tell
    "the reporter said nobody was hurt" apart from "nobody was asked". A plain
    ``bool()`` cannot: it collapses both onto False, and it also reports True for
    the string ``"no"`` -- the defect fixed on the incident path in #1412. The RTA
    form currently posts real JSON booleans, so that string case is latent here
    rather than live, but it is one template revision away.

    An unrecognised answer is read as True: a value nobody anticipated must not
    silently downgrade an injury.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        answer = value.strip().lower()
        if not answer:
            return None
        if answer in _FALSY_ANSWERS:
            return False
        if answer in _TRUTHY_ANSWERS:
            return True
        return True
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, (list, tuple, set, dict)):
        # An injury detail structure: populated means injury, empty means nothing told.
        return True if value else None
    return True


def interpret_rta_yes_no_answer(value: Any) -> Optional[bool]:
    """Read a plain yes/no portal toggle as True / False / unknown.

    Separate from :func:`interpret_rta_injury_answer` because the two have
    different safe directions. An unrecognised *injury* answer must fail towards
    injury; an unrecognised answer to "was a third party involved" has no safe
    direction to guess in, so it stays unknown. ``bool()`` cannot be used for
    either: the published templates post the strings ``"yes"``/``"no"`` and
    ``bool("no")`` is True — the defect fixed on the incident path in #1412.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        answer = value.strip().lower()
        if answer in _FALSY_ANSWERS:
            return False
        if answer in _TRUTHY_ANSWERS:
            return True
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def read_reported_bool(value: Any) -> Optional[bool]:
    """Accept only a real boolean; anything else is 'not reported'.

    Used for operational facts (e.g. vehicle drivability) where there is no
    safe direction to guess in and a wrong guess is worse than an honest null.
    """
    return value if isinstance(value, bool) else None


def derive_portal_rta_severity(
    *,
    driver_injured: Optional[bool],
    third_party_injured: Optional[bool],
) -> RTASeverity:
    """Pick an injury-outcome severity from reported injury evidence alone.

    Mirrors the Excel import path, which records ``MINOR_INJURY`` when an injury
    was reported and ``DAMAGE_ONLY`` otherwise. ``SERIOUS_INJURY`` and ``FATAL``
    are clinical determinations made by staff after assessment and are never
    assigned at intake -- intake records that someone was hurt, not how badly.
    """
    if driver_injured is True or third_party_injured is True:
        return RTASeverity.MINOR_INJURY
    return RTASeverity.DAMAGE_ONLY
