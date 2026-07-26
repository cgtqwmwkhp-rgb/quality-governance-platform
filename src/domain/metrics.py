"""Ratio metrics that keep "nothing measured" distinguishable from "perfect".

PX-216: several scoring paths divide-guarded a zero denominator to ``100``, so an
empty dataset rendered as full compliance. For a governance platform that is the
most dangerous failure mode available — it asserts a clean bill of health for
something that was never checked. "0 failures out of 0 checks" is not 100%
compliant; it is not measured.

Every ratio-derived percentage should therefore go through
:func:`percentage_or_none` or :func:`compliance_percentage_or_none`, both of which
return ``None`` — never ``0``, never ``100`` — when there is nothing to divide by.
API schemas expose those fields as ``Optional[float]`` and the presentation layer
renders ``None`` as an explicit "not measured" state (an em dash), so the empty
case survives all the way to the screen.
"""

from __future__ import annotations

from typing import Optional, Union

__all__ = ["percentage_or_none", "compliance_percentage_or_none"]

Number = Union[int, float]


def percentage_or_none(
    part: Optional[Number],
    whole: Optional[Number],
    *,
    digits: Optional[int] = 2,
) -> Optional[float]:
    """Return ``part / whole`` as a percentage, or ``None`` when nothing was measured.

    ``None`` is returned whenever *whole* is missing, zero or negative — i.e. there
    is no population to express *part* as a share of. A missing *part* over a real
    population is a genuine zero, so it yields ``0.0``.

    The result is deliberately not clamped to 0-100: a *part* larger than *whole*
    signals a counting bug upstream and should stay visible rather than be rounded
    into a plausible-looking number.

    Args:
        part: The measured subset (e.g. passed checks).
        whole: The measured population (e.g. total checks).
        digits: Decimal places to round to, or ``None`` to skip rounding.
    """
    if whole is None or whole <= 0:
        return None
    value = (float(part or 0) / float(whole)) * 100.0
    return round(value, digits) if digits is not None else value


def compliance_percentage_or_none(
    failing: Optional[Number],
    total: Optional[Number],
    *,
    digits: Optional[int] = 2,
) -> Optional[float]:
    """Return the share of *total* that is **not** failing, or ``None`` if unmeasured.

    The inverse form of :func:`percentage_or_none`, for the common
    "compliance = 1 - failures/total" shape. Zero failures out of zero checks is
    ``None``, not 100%.
    """
    if total is None or total <= 0:
        return None
    return percentage_or_none(float(total) - float(failing or 0), total, digits=digits)
