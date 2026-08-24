"""Lookup categories whose codes are also API enum values (PX-281/282).

Most lookup categories are free-form reference data: an admin can call a
customer whatever they like. A handful are not. When a form renders a lookup
category into a select and submits the chosen ``lookup_options.code`` verbatim
as an enum-validated request field, the category stops being reference data and
becomes half of a contract — every active code has to be a member of that enum
or whoever picks it gets an HTTP 422.

PX-281/282 is that failure in its purest form. ``complaint_types`` offered
exactly one option, ``workmanship``, which ``ComplaintType`` has never
contained, so ``POST /api/v1/complaints/`` rejected the only value the form
could produce and no complaint could be submitted through the UI at all.
``incident_types`` (R22-01) carried five more codes with the same problem.

Naming the pairings here gives the seed data, the repair migration, the
admin write guard and the contract test one definition to agree with instead of
four restatements of it.

``severity_levels`` is the third entry, added by B-9. It is unusual in that one
category feeds three differently-named fields — incident ``severity``, complaint
``priority`` and near-miss ``potential_severity`` — which is why it sat outside
this registry while they disagreed: the dropdown offered ``negligible`` and only
incident severity accepted it. B-9 settled that as a product decision (one shared
severity set across the three) rather than as three separate taxonomies, so the
category now has a single enum behind it and belongs here. ``IncidentSeverity`` is
that enum; ``ComplaintPriority`` mirrors it member for member. The RTA harm scale
(``RTASeverity``) and audit finding grading are *not* part of the shared set —
they measure different things and are not fed by this lookup.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable
from dataclasses import dataclass

from src.domain.exceptions import ValidationError
from src.domain.models.complaint import ComplaintType
from src.domain.models.incident import IncidentSeverity, IncidentType


@dataclass(frozen=True, slots=True)
class EnumBackedLookup:
    """One lookup category and the enum-validated field its codes are sent as."""

    category: str
    enum_class: type[enum.Enum]
    request_field: str
    ticket: str

    @property
    def allowed_codes(self) -> tuple[str, ...]:
        """Every code this category may contain, in enum declaration order."""
        return tuple(str(member.value) for member in self.enum_class)


ENUM_BACKED_LOOKUPS: tuple[EnumBackedLookup, ...] = (
    EnumBackedLookup(
        category="complaint_types",
        enum_class=ComplaintType,
        request_field="complaint_type",
        ticket="PX-281/282",
    ),
    EnumBackedLookup(
        category="incident_types",
        enum_class=IncidentType,
        request_field="incident_type",
        ticket="R22-01",
    ),
    EnumBackedLookup(
        category="severity_levels",
        enum_class=IncidentSeverity,
        request_field="severity",
        ticket="B-9",
    ),
)

ENUM_BACKED_CATEGORIES: tuple[str, ...] = tuple(lookup.category for lookup in ENUM_BACKED_LOOKUPS)


def lookup_for_category(category: str) -> EnumBackedLookup | None:
    """Return the contract for ``category``, or None if it is free-form data."""
    for lookup in ENUM_BACKED_LOOKUPS:
        if lookup.category == category:
            return lookup
    return None


def allowed_codes(category: str) -> tuple[str, ...]:
    """Codes accepted by the field ``category`` feeds; empty when unconstrained."""
    lookup = lookup_for_category(category)
    return lookup.allowed_codes if lookup is not None else ()


def rejected_codes(category: str, codes: Iterable[str]) -> tuple[str, ...]:
    """Which of ``codes`` the field behind ``category`` would reject, sorted.

    Comparison is case-insensitive because the columns backing these fields are
    ``CaseInsensitiveEnum``, which lowercases on the way in. A free-form
    category constrains nothing, so nothing is rejected.
    """
    lookup = lookup_for_category(category)
    if lookup is None:
        return ()
    permitted = {code.lower() for code in lookup.allowed_codes}
    return tuple(sorted({code for code in codes if code.strip().lower() not in permitted}))


def ensure_enum_backed_code(category: str, code: str) -> None:
    """Reject an admin-authored code the paired API field would 422 on (R22-03).

    Free-form categories are unconstrained and pass through. Enum-backed ones
    raise ``ValidationError`` (HTTP 422) naming the allowed values, so the
    dropdown cannot drift back into the PX-281/282 shape via the admin UI.
    """
    lookup = lookup_for_category(category)
    if lookup is None:
        return
    if not rejected_codes(category, (code,)):
        return
    allowed = ", ".join(lookup.allowed_codes)
    raise ValidationError(
        f"Lookup category '{category}' feeds '{lookup.request_field}' "
        f"({lookup.enum_class.__name__}); '{code}' is not an allowed value. "
        f"Allowed: {allowed}.",
        details={
            "category": category,
            "code": code,
            "request_field": lookup.request_field,
            "allowed": list(lookup.allowed_codes),
            "ticket": lookup.ticket,
        },
    )
