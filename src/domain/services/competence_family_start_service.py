"""Start a family demonstration from a plant board cell (CB-UI-3).

CB-UI-1 put the Plant board on the LIVE competence API and CB-UI-2 gave an
IT-Admin the screen that binds one published template to one PAMS
characteristic per mode. The cell still could not *start* anything. This module
is the part of that start which has to be true regardless of which client asks.

Three rules live here rather than in a route, because a rule enforced in one
handler is a rule a second handler does not have:

**One run type demonstrates.** ``AssessmentRun`` completion is the only path in
this repo that writes a ``CompetenceDemonstration`` (see
``assessments.complete_assessment`` → ``record_assessment_demonstration_async``).
So starting a demonstration means creating an ``AssessmentRun`` against the
bound template — the mode picks *which* bound template, it does not pick a
second kind of run. Audit runs carry an unrelated ``assessment_mode``
(full / spot_check) and write no demonstration; routing a family assessment
through them would need a second overlay writer, which is the one thing this
slice must not add.

**The assessor gate is a property of the bind, not of the screen.** Anyone who
can create an assessment can name a bound ``template_id`` directly, so gating
only the board's own start endpoint would leave ``POST /api/v1/assessments/``
as an unguarded way in. ``enforce_bound_template_assessor_gate_async`` is
therefore called from the shared create path and applies to *any* run against a
bound template.

**Issued is proven, never assumed.** "Issued" means a row for that engineer and
characteristic in the current PAMS competence snapshot — the same read the board
paints its cells from. There is no parallel QGP competence table to consult and
none is created. Where issuance cannot be *proven* the gate refuses: no employee
record, no snapshot, or no row all fail closed, because "we could not check" and
"they are issued" are different facts and only one of them is a permission.

QGP never writes PAMS. Nothing here opens a PAMS connection, a pass records a
QGP demonstration only, and a family fail still opens the CB-PR4 revoke change
request for the IT-Admin mailbox rather than un-issuing anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from sqlalchemy import select

from src.core.config import settings
from src.domain.exceptions import AuthorizationError, BadRequestError
from src.domain.models.competence_assessment_bind import BIND_MODES, FIELD_MODE, CompetenceAssessmentBind
from src.domain.models.engineer import Engineer
from src.domain.services.competence_demonstration_service import get_bind_for_template_async
from src.domain.services.pams_competence_snapshot_service import load_current_snapshot_async

#: Evidence keys accepted on a family run. Identification of the machine the
#: demonstration happened on — not an OEM catalogue, not a board column, and
#: never a competence claim of its own. CB-OEM owns make/model as data.
PLANT_EVIDENCE_FIELDS: tuple[str, ...] = ("make", "model", "serial", "pams_plant_id")

#: Long enough for a real serial plate, short enough that the JSON column cannot
#: be used as free storage by a client that ignores the schema.
PLANT_EVIDENCE_MAX_LEN = 120

NO_BIND_FOR_CHARACTERISTIC = (
    "{characteristic} has no family assessment template yet, so there is nothing to start. "
    "An IT-Admin maps a published template to it on Admin → Competence binds."
)
NO_BIND_FOR_MODE = (
    "{characteristic} has no {mode} template bound, so there is no {mode} demonstration to start. "
    "Bound modes for it: {bound}. An IT-Admin maps the missing one on Admin → Competence binds."
)
ENGINEER_NOT_ON_THE_BOARD = (
    "That person has no QGP employee record, so a demonstration has nothing to be recorded against. "
    "They stay on the board as a PAMS row; linking them is an IT-Admin change, not an assessment."
)
ASSESSOR_IS_THE_ENGINEER = (
    "You cannot assess yourself. A demonstration needs a second person to witness it, "
    "so the assessor and the engineer being assessed must be different people."
)
ASSESSOR_HAS_NO_EMPLOYEE_RECORD = (
    "Your user account is not linked to a QGP employee record, so QGP cannot prove PAMS has issued "
    "you this skill. Assessing requires that proof — ask an IT-Admin to link your employee record."
)
ASSESSOR_SNAPSHOT_MISSING = (
    "No PAMS competence snapshot has been loaded, so QGP cannot prove PAMS has issued you this skill. "
    "This refuses rather than assumes: an unproven issue is not the same as an issued one."
)
ASSESSOR_NOT_ISSUED = (
    "PAMS has not issued you {characteristic}, so you cannot assess it. "
    "Issuance lives in PAMS — QGP reads it and never writes it."
)


@dataclass(frozen=True)
class AssessorGate:
    """The gate's answer, with the sentence a refusal is entitled to.

    ``reason`` is the message shown to the assessor and is written to be true on
    its own: a refusal must say which of the four ways it failed, because
    "not issued" and "we could not check" call for different actions.
    """

    allowed: bool
    characteristic_key: str
    assessor_engineer_id: Optional[int] = None
    reason: Optional[str] = None


def clean_mode(value: str | None) -> str:
    """Default to field, matching the bind service's own leniency for CB-PR4 rows."""
    mode = (value or FIELD_MODE).strip().lower()
    if mode not in BIND_MODES:
        raise BadRequestError(f"mode must be one of {', '.join(BIND_MODES)}.")
    return mode


def normalise_plant_evidence(values: Mapping[str, Any] | None) -> dict[str, str] | None:
    """Keep only the evidence fields the assessor actually filled in.

    An all-blank form stores nothing rather than a dict of empty strings, so a
    run with no evidence is honestly indistinguishable from one where the boxes
    were tabbed through. Unknown keys are dropped here as well as refused by the
    schema, because this is also the normaliser for anything already on a row.
    """
    if not values:
        return None
    cleaned: dict[str, str] = {}
    for field in PLANT_EVIDENCE_FIELDS:
        raw = values.get(field)
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        cleaned[field] = text[:PLANT_EVIDENCE_MAX_LEN]
    return cleaned or None


async def list_binds_for_characteristic_async(
    db: Any,
    *,
    tenant_id: int,
    characteristic_key: str,
) -> list[CompetenceAssessmentBind]:
    result = await db.scalars(
        select(CompetenceAssessmentBind).where(
            CompetenceAssessmentBind.tenant_id == tenant_id,
            CompetenceAssessmentBind.characteristic_key == characteristic_key,
        )
    )
    return list(result.all())


def bound_modes_by_characteristic(binds: list[CompetenceAssessmentBind]) -> dict[str, list[str]]:
    """Which modes each characteristic can be started in.

    Ordered by ``BIND_MODES`` rather than insertion or id so the board renders
    the same picker every load. A characteristic absent from this map is
    *unbound*: the board must list it and say no template is mapped yet, which
    is a gap in QGP's mapping and not a finding against anyone.
    """
    found: dict[str, set[str]] = {}
    for bind in binds:
        found.setdefault(bind.characteristic_key, set()).add(bind.mode or FIELD_MODE)
    return {key: [mode for mode in BIND_MODES if mode in modes] for key, modes in found.items()}


async def resolve_startable_bind_async(
    db: Any,
    *,
    tenant_id: int,
    characteristic_key: str,
    mode: str | None,
) -> CompetenceAssessmentBind:
    """The bind whose template a start will run, or a refusal that says why.

    Unbound and bound-in-the-other-mode are different sentences on purpose. The
    first tells an IT-Admin to map the characteristic; the second tells them the
    mapping exists and it is the mode that is missing. Collapsing them into one
    "cannot start" would send the reader to the wrong screen.
    """
    key = (characteristic_key or "").strip()
    if not key:
        raise BadRequestError("characteristic_key is required.")
    wanted = clean_mode(mode)

    binds = await list_binds_for_characteristic_async(db, tenant_id=tenant_id, characteristic_key=key)
    if not binds:
        raise BadRequestError(NO_BIND_FOR_CHARACTERISTIC.format(characteristic=key))

    match = next((bind for bind in binds if (bind.mode or FIELD_MODE) == wanted), None)
    if match is None:
        bound = ", ".join(bound_modes_by_characteristic(binds).get(key, []))
        raise BadRequestError(NO_BIND_FOR_MODE.format(characteristic=key, mode=wanted, bound=bound))
    return match


async def resolve_assessor_engineer_async(
    db: Any,
    *,
    tenant_id: int,
    user_id: int | None,
) -> Engineer | None:
    """The assessor's own employee record, which is what the snapshot is keyed on.

    None is a refusal, not an empty result: the PAMS snapshot joins on
    ``engineer_id``, so a user with no employee record has no row that could
    prove issuance either way.
    """
    if user_id is None:
        return None
    result = await db.scalars(
        select(Engineer).where(
            Engineer.user_id == user_id,
            Engineer.tenant_id == tenant_id,
        )
    )
    return result.first()


async def issued_characteristics_async(
    db: Any,
    *,
    tenant_id: int,
    engineer_id: int | None,
) -> set[str] | None:
    """Characteristics the current PAMS snapshot issues to this engineer.

    ``None`` means the question could not be answered — there is no snapshot, or
    no engineer to key one on. An empty set means the snapshot was read and holds
    nothing for them. Callers must keep those apart: only one of them is a fact
    about the person.
    """
    if engineer_id is None:
        return None
    snapshot, rows = await load_current_snapshot_async(db, tenant_id)
    if snapshot is None:
        return None
    return {row.characteristic_key for row in rows if row.engineer_id == engineer_id and row.characteristic_key}


async def check_assessor_gate_async(
    db: Any,
    *,
    tenant_id: int,
    assessor_user_id: int | None,
    engineer_id: int,
    characteristic_key: str,
) -> AssessorGate:
    """Assessor ≠ engineer, and the assessor is PAMS-issued on this characteristic.

    Order matters for the sentence the caller gets back. Self-assessment is
    checked before issuance because "you cannot assess yourself" is the accurate
    reason even when the person is issued, and it is the one they can act on.
    """
    key = (characteristic_key or "").strip()
    assessor = await resolve_assessor_engineer_async(db, tenant_id=tenant_id, user_id=assessor_user_id)
    if assessor is None:
        return AssessorGate(allowed=False, characteristic_key=key, reason=ASSESSOR_HAS_NO_EMPLOYEE_RECORD)

    if assessor.id == engineer_id:
        # Compared as employee records rather than user ids: an engineer with no
        # linked user account, or a second account, must not become assessable
        # by themselves through the gap.
        return AssessorGate(
            allowed=False,
            characteristic_key=key,
            assessor_engineer_id=assessor.id,
            reason=ASSESSOR_IS_THE_ENGINEER,
        )

    issued = await issued_characteristics_async(db, tenant_id=tenant_id, engineer_id=assessor.id)
    if issued is None:
        return AssessorGate(
            allowed=False,
            characteristic_key=key,
            assessor_engineer_id=assessor.id,
            reason=ASSESSOR_SNAPSHOT_MISSING,
        )
    if key not in issued:
        return AssessorGate(
            allowed=False,
            characteristic_key=key,
            assessor_engineer_id=assessor.id,
            reason=ASSESSOR_NOT_ISSUED.format(characteristic=key),
        )
    return AssessorGate(allowed=True, characteristic_key=key, assessor_engineer_id=assessor.id)


async def enforce_bound_template_assessor_gate_async(
    db: Any,
    *,
    tenant_id: int | None,
    assessor_user_id: int | None,
    engineer_id: int,
    template_id: int,
) -> AssessorGate | None:
    """Gate any assessment run whose template is bound to a PAMS characteristic.

    Returns None when the gate does not apply, which is the whole of the
    flag-off behaviour: with ``COMPETENCE_BOARD_ENABLED`` false the bind table
    means nothing, so creating an assessment behaves exactly as it did before
    this slice. An unbound template is also None — a run that will never write a
    demonstration is not a family assessment and gets no new rules.

    Raises ``AuthorizationError`` (403) rather than returning a refusal, because
    every caller of this function has to stop.
    """
    if not settings.competence_board_enabled:
        return None
    if tenant_id is None:
        return None

    bind = await get_bind_for_template_async(db, tenant_id=tenant_id, template_id=template_id)
    if bind is None:
        return None

    gate = await check_assessor_gate_async(
        db,
        tenant_id=tenant_id,
        assessor_user_id=assessor_user_id,
        engineer_id=engineer_id,
        characteristic_key=bind.characteristic_key,
    )
    if not gate.allowed:
        raise AuthorizationError(
            gate.reason or ASSESSOR_NOT_ISSUED.format(characteristic=bind.characteristic_key),
            details={
                "characteristic_key": bind.characteristic_key,
                "mode": bind.mode or FIELD_MODE,
                "engineer_id": engineer_id,
            },
        )
    return gate
