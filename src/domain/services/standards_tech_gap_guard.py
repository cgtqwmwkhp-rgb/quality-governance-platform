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
A document still cannot cover these cells. Attestation kinds travel on a separate
typed channel (``attestations=``) supplied at read time by the Entra MFA reader —
never from ``ComplianceEvidenceLink.entity_type``, which is operator-writable.
:data:`TECHNICAL_ATTESTATION_ENTITY_TYPES` therefore stays empty: putting a kind
name in that set would let anyone type it onto a CEL row and turn A.8.5 green.

Cyber Essentials Plus is a witnessed hands-on test. Graph is not a Plus
assessment, so ``cep`` is short-circuited before any kind mapping. Cyber
Essentials ``user_access_control`` needs three things; MFA is only one of them,
so Entra MFA can partially attest that cell and never cover it.

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

#: Entity types that would read configuration from the system under test.
#: Stays empty on purpose — see the module docstring. Covering attestations
#: are passed as ``assess(..., attestations=)``, not as CEL entity types.
TECHNICAL_ATTESTATION_ENTITY_TYPES: frozenset[str] = frozenset()

#: Framework ids that a Graph/IdP read can never cover. Cyber Essentials Plus
#: tests MFA by hand; adding a kind that lists ``cep`` must still fail closed.
HANDS_ON_TEST_FRAMEWORKS: frozenset[str] = frozenset({CYBER_ESSENTIALS_PLUS_ID})

CEP_WITNESSED_TEST_REASON = "cyber_essentials_plus_requires_witnessed_test"


@dataclass(frozen=True)
class TechnicalAttestationKind:
    """What one live attestation kind is allowed to say about a requirement."""

    kind: str
    covers_requirement_keys: tuple[str, ...]
    covers_frameworks: tuple[str, ...]
    partially_covers_requirement_keys: tuple[str, ...]
    unattested_elements: tuple[str, ...] = ()


TECHNICAL_ATTESTATION_KINDS: dict[str, TechnicalAttestationKind] = {
    "entra_mfa": TechnicalAttestationKind(
        kind="entra_mfa",
        covers_requirement_keys=("27001-a.8.5",),
        covers_frameworks=("27001",),
        partially_covers_requirement_keys=(f"{CYBER_ESSENTIALS_ID}-user_access_control",),
        unattested_elements=(
            "individually assigned accounts",
            "separated administrative accounts",
        ),
    ),
}


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

    #: True only when a typed attestation kind covers this cell's requirement.
    covered: bool
    #: True when the requirement is technical but is not fully attested.
    stub: bool
    requirement: Optional[TechnicalRequirement]
    reason: str
    document_only_entity_types: tuple[str, ...] = ()
    #: ``pass`` / ``partial`` when a live kind was considered; otherwise None.
    attestation_status: Optional[str] = None
    attested_kind: Optional[str] = None
    unattested_elements: tuple[str, ...] = ()

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
            "attestation_status": self.attestation_status,
            "attested_kind": self.attested_kind,
            "unattested_elements": list(self.unattested_elements),
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
    attestations: Iterable[str] = (),
) -> TechGapDecision:
    """Can the offered evidence types cover this cell?

    Non-technical cells are returned untouched (``is_technical`` False) so callers
    can apply this to every cell without it having an opinion about most of them.

    ``entity_types`` is the CEL-derived, document-only channel. ``attestations``
    is a tuple of kind names from the live reader — never from the database.
    """
    requirement = requirement_for(framework, clause_number)
    offered = tuple(sorted({str(t).strip().lower() for t in entity_types if str(t).strip()}))
    documents = tuple(t for t in offered if t in DOCUMENT_ONLY_ENTITY_TYPES)
    cell_fw = (framework or "").strip().lower()

    if requirement is None:
        return TechGapDecision(
            covered=False,
            stub=False,
            requirement=None,
            reason="not a technical requirement — TechGapGuard has no opinion",
        )

    if cell_fw in HANDS_ON_TEST_FRAMEWORKS:
        return TechGapDecision(
            covered=False,
            stub=True,
            requirement=requirement,
            reason=CEP_WITNESSED_TEST_REASON,
            document_only_entity_types=documents,
        )

    offered_kinds = tuple(str(kind).strip().lower() for kind in attestations if str(kind).strip())
    partial: Optional[TechnicalAttestationKind] = None
    for kind_name in offered_kinds:
        spec = TECHNICAL_ATTESTATION_KINDS.get(kind_name)
        if spec is None:
            continue
        if requirement.key in spec.covers_requirement_keys and cell_fw in spec.covers_frameworks:
            return TechGapDecision(
                covered=True,
                stub=False,
                requirement=requirement,
                reason=f"technical attestation offered ({spec.kind})",
                document_only_entity_types=documents,
                attestation_status="pass",
                attested_kind=spec.kind,
            )
        if requirement.key in spec.partially_covers_requirement_keys:
            partial = spec

    if partial is not None:
        unattested = partial.unattested_elements
        return TechGapDecision(
            covered=False,
            stub=True,
            requirement=requirement,
            reason=(
                f"{requirement.title} is partially attested ({partial.kind}): MFA enforced. "
                f"Not attested: {', '.join(unattested)}."
            ),
            document_only_entity_types=documents,
            attestation_status="partial",
            attested_kind=partial.kind,
            unattested_elements=unattested,
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
