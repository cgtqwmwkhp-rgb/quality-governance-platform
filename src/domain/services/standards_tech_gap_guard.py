"""TechGapGuard: a document cannot close a technical control.

Wave 2 PR-C. Gap 5 of PEL-HSEQ-5064 reads: *"A.8.5 secure authentication, and
Cyber Essentials user access control — MFA WAS FOUND FAILING IN PRODUCTION and
Conditional Access does not exist."* The failure mode this guards is the obvious
one: somebody links the access control procedure PDF to A.8.5 and the clause turns
green, while multi-factor authentication is still off. Cyber Essentials Plus tests
that control by hand, so the green square is worse than a red one — it is a green
square an assessor will disprove in minutes.

The rule
--------
For the requirements listed in :data:`TECHNICAL_REQUIREMENTS`, a document, policy
or controlled document is *supporting* evidence and never *covering* evidence.
Only a technical attestation — a configuration read from the system under test —
can cover them.

The honest part
--------------
This platform has no source of technical attestation today. There is no Conditional
Access reader, no MFA enrolment report and no vulnerability scan import, so
:data:`TECHNICAL_ATTESTATION_ENTITY_TYPES` is empty and every assessment here
returns ``covered=False`` with ``stub=True``. That is the accurate answer, and it
is recorded as a stub rather than as a passing check so it cannot be mistaken for
one. When an attestation source lands, it is added to that set and these
requirements become answerable rather than merely blocked.

Matrix ids
----------
``ce`` and ``cep`` are the Cyber Essentials and Cyber Essentials Plus columns in
the matrix chrome. :data:`TECHNICAL_REQUIREMENTS` is keyed on those same ids so a
technical gap lands on the column an assessor will test.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

#: Matrix column ids for Cyber Essentials / Cyber Essentials Plus (NCSC scheme).
CYBER_ESSENTIALS_ID = "ce"
CYBER_ESSENTIALS_PLUS_ID = "cep"

#: Entity types that are documents in some form. They can support a technical
#: control but cannot demonstrate one is switched on.
DOCUMENT_ONLY_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "document",
        "policy",
        "controlled_document",
        "controlled_document_version",
        "document_version",
        "evidence_asset",
        "procedure",
    }
)

#: Entity types that read configuration from the system under test. Empty today —
#: see the module docstring. Adding a type here is what makes a technical
#: requirement answerable, and should come with the reader that populates it.
TECHNICAL_ATTESTATION_ENTITY_TYPES: frozenset[str] = frozenset()


@dataclass(frozen=True)
class TechnicalRequirement:
    """A control that configuration must prove, not prose."""

    key: str
    title: str
    frameworks: tuple[str, ...]
    #: What would actually evidence it, in the source's terms.
    attestation_needed: str
    #: The position PEL-HSEQ-5064 records against it.
    source_position: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "frameworks": list(self.frameworks),
            "attestation_needed": self.attestation_needed,
            "source_position": self.source_position,
        }


#: Keyed by catalogue-shaped clause key. Only the requirements PEL-HSEQ-5064 names
#: as technical are listed; this is not an attempt to classify all 93 Annex A
#: controls, which sheet 03 covers and this edition does not import.
TECHNICAL_REQUIREMENTS: dict[str, TechnicalRequirement] = {
    "27001-a.8.5": TechnicalRequirement(
        key="27001-a.8.5",
        title="Secure authentication",
        frameworks=("27001", CYBER_ESSENTIALS_ID, CYBER_ESSENTIALS_PLUS_ID),
        attestation_needed=(
            "Multi-factor authentication enforced on all cloud services, read from "
            "the identity provider — not a procedure describing that it should be."
        ),
        source_position=(
            "Gap 5: MFA was found failing in production and Conditional Access does "
            "not exist. Fails the Cyber Essentials control as written; Cyber "
            "Essentials Plus tests it hands on."
        ),
    ),
    f"{CYBER_ESSENTIALS_ID}-user_access_control": TechnicalRequirement(
        key=f"{CYBER_ESSENTIALS_ID}-user_access_control",
        title="User access control",
        frameworks=(CYBER_ESSENTIALS_ID, CYBER_ESSENTIALS_PLUS_ID, "27001"),
        attestation_needed=(
            "Accounts assigned to individuals, administrative accounts separate, and "
            "multi-factor authentication on all cloud services, verified against the "
            "live directory."
        ),
        source_position=(
            "Gap 5: LIVE GAP — MFA was found failing in production and Conditional " "Access does not exist."
        ),
    ),
}


@dataclass(frozen=True)
class TechGapDecision:
    """Whether the offered evidence can cover a technical requirement."""

    #: True only when a technical attestation was offered. Never true today.
    covered: bool
    #: True when the requirement is technical but no attestation source exists.
    stub: bool
    requirement: Optional[TechnicalRequirement]
    reason: str
    document_only_entity_types: tuple[str, ...] = ()

    @property
    def is_technical(self) -> bool:
        return self.requirement is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "covered": self.covered,
            "stub": self.stub,
            "is_technical": self.is_technical,
            "reason": self.reason,
            "requirement": self.requirement.to_dict() if self.requirement else None,
            "document_only_entity_types": list(self.document_only_entity_types),
        }


def normalise_clause_key(framework: str, clause_number: str) -> str:
    return f"{(framework or '').strip().lower()}-{str(clause_number or '').strip().lower()}"


def requirement_for(framework: str, clause_number: str) -> Optional[TechnicalRequirement]:
    """The technical requirement at this cell, if the source names one."""
    key = normalise_clause_key(framework, clause_number)
    requirement = TECHNICAL_REQUIREMENTS.get(key)
    if requirement is not None:
        return requirement
    # A.8.5 is reachable as "a.8.5" or "A.8.5" in either framework spelling.
    bare = str(clause_number or "").strip().lower()
    for candidate in TECHNICAL_REQUIREMENTS.values():
        if candidate.key.endswith(f"-{bare}") and (framework or "").strip().lower() in candidate.frameworks:
            return candidate
    return None


def assess(
    *,
    framework: str,
    clause_number: str,
    entity_types: Iterable[str] = (),
) -> TechGapDecision:
    """Can the offered evidence types cover this cell?

    Non-technical cells are returned untouched (``is_technical`` False) so callers
    can apply this to every cell without it having an opinion about most of them.
    """
    requirement = requirement_for(framework, clause_number)
    offered = tuple(sorted({str(t).strip().lower() for t in entity_types if str(t).strip()}))

    if requirement is None:
        return TechGapDecision(
            covered=False,
            stub=False,
            requirement=None,
            reason="not a technical requirement — TechGapGuard has no opinion",
        )

    attestations = tuple(t for t in offered if t in TECHNICAL_ATTESTATION_ENTITY_TYPES)
    documents = tuple(t for t in offered if t in DOCUMENT_ONLY_ENTITY_TYPES)

    if attestations:
        return TechGapDecision(
            covered=True,
            stub=False,
            requirement=requirement,
            reason=f"technical attestation offered ({', '.join(attestations)})",
            document_only_entity_types=documents,
        )

    if documents:
        return TechGapDecision(
            covered=False,
            stub=True,
            requirement=requirement,
            reason=(
                f"{requirement.title} is a technical control: "
                f"{', '.join(documents)} evidence describes it but cannot show it is "
                "in force. " + requirement.source_position
            ),
            document_only_entity_types=documents,
        )

    return TechGapDecision(
        covered=False,
        stub=True,
        requirement=requirement,
        reason=(
            f"{requirement.title} needs a technical attestation and this platform has "
            "no attestation source yet. " + requirement.source_position
        ),
    )
