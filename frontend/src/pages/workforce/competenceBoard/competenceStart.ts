/**
 * Pure startability model for a plant board cell (CB-UI-3).
 *
 * Extracted for the same reason CB-UI-1 extracted the cell model: this is the
 * part that can quietly lie. A square that cannot be started has to say *which*
 * of five different reasons applies, and four of them are statements about the
 * viewer or about QGP's mapping rather than about the person on the row. Getting
 * that wrong reintroduces the exact defect CB-UI-1 removed from this board — a
 * square that reads like a finding when it is really an absence.
 *
 * The order of the checks is the order of the reader's questions:
 *
 * 1. **Wrong family.** Atlas courses are issued by a course pass; there is no
 *    PAMS characteristic to bind, so nothing on that tab is startable.
 * 2. **Unbound column.** True for everyone looking at it, so it outranks any
 *    fact about the viewer. The copy sends an IT-Admin to the CB-UI-2 mapping
 *    screen and never mentions failure.
 * 3. **Unlinked person.** A demonstration is keyed on `engineers.id`; a PAMS row
 *    with no employee record has nothing to attach one to.
 * 4. **The viewer cannot assess at all** — no employee record of their own, or
 *    no snapshot to prove issuance from. The server's own sentence is used.
 * 5. **The viewer cannot assess *this*** — it is themselves, or PAMS has not
 *    issued it to them.
 *
 * None of this is the authority. The gate is enforced server-side on create, so
 * a client that offers a start anyway gets a 403 rather than a run.
 */
import type { CompetenceBindMode } from '../../../api/competenceBindClient'
import type {
  CompetenceBoardAssessor,
  CompetenceBoardColumn,
  CompetenceBoardFamily,
  CompetenceBoardPerson,
} from '../../../api/competenceBoardClient'

export type CellStartability =
  | { status: 'startable'; modes: CompetenceBindMode[] }
  | { status: 'blocked'; reason: string }

export const NOT_PLANT_FAMILY =
  'Starting a demonstration applies to the Plant family. People courses are issued in Atlas and QGP records no assessment against them.'

/**
 * Deliberately worded as a gap in QGP's mapping. "No template yet" is a
 * statement about this system; "failed" would be a statement about a person,
 * and the two must not be confusable in a square.
 */
export const NO_FAMILY_TEMPLATE =
  'No family assessment template is mapped to this characteristic yet, so there is nothing to start. An IT-Admin maps one on Admin → Competence binds.'

export const PERSON_NOT_LINKED =
  'This person has no QGP employee record, so a demonstration has nothing to be recorded against. Linking them is an IT-Admin change, not an assessment.'

export const CANNOT_ASSESS_SELF =
  'You cannot assess yourself. A demonstration needs a second person to witness it.'

export const ASSESSOR_NOT_ISSUED_PREFIX = 'PAMS has not issued you'

export function assessorNotIssued(characteristicLabel: string): string {
  return `${ASSESSOR_NOT_ISSUED_PREFIX} ${characteristicLabel}, so you cannot assess it. Issuance lives in PAMS — QGP reads it and never writes it.`
}

/** Modes a column offers, tolerating an older server that sends none. */
export function boundModes(column: Pick<CompetenceBoardColumn, 'bound_modes'>): CompetenceBindMode[] {
  return Array.isArray(column.bound_modes) ? column.bound_modes : []
}

export function isUnbound(column: Pick<CompetenceBoardColumn, 'bound_modes'>): boolean {
  return boundModes(column).length === 0
}

export function cellStartability({
  family,
  column,
  person,
  assessor,
}: {
  family: CompetenceBoardFamily
  column: CompetenceBoardColumn
  person: Pick<CompetenceBoardPerson, 'engineer_id' | 'mapped'>
  assessor: CompetenceBoardAssessor | null | undefined
}): CellStartability {
  if (family !== 'pams') return { status: 'blocked', reason: NOT_PLANT_FAMILY }

  const modes = boundModes(column)
  if (modes.length === 0) return { status: 'blocked', reason: NO_FAMILY_TEMPLATE }

  if (!person.mapped || person.engineer_id == null) {
    return { status: 'blocked', reason: PERSON_NOT_LINKED }
  }

  // An absent assessor block is treated as "cannot prove it", not as "allowed".
  // A server that has not been upgraded must not silently open the gate.
  if (!assessor) return { status: 'blocked', reason: assessorNotIssued(column.label) }
  if (assessor.blocked_reason) return { status: 'blocked', reason: assessor.blocked_reason }
  if (assessor.engineer_id == null) return { status: 'blocked', reason: assessorNotIssued(column.label) }
  if (assessor.engineer_id === person.engineer_id) {
    return { status: 'blocked', reason: CANNOT_ASSESS_SELF }
  }

  const issued = Array.isArray(assessor.issued_characteristic_keys)
    ? assessor.issued_characteristic_keys
    : []
  if (!issued.includes(column.key)) {
    return { status: 'blocked', reason: assessorNotIssued(column.label) }
  }

  return { status: 'startable', modes }
}

/**
 * The sentence appended to the cell's existing screen-reader summary.
 *
 * A startable cell gets an action; a blocked one gets the reason. Nothing is
 * silently omitted, because a square that is a button for one person and inert
 * for another with no explanation is the thing this slice must not ship.
 */
export function startabilitySummary(startability: CellStartability): string {
  if (startability.status === 'startable') {
    return `can start ${startability.modes.join(' or ')} assessment`
  }
  return startability.reason
}

export const MODE_LABEL: Record<CompetenceBindMode, string> = {
  field: 'Field assessment',
  induction: 'Induction',
}

/** Which mode a freshly opened start form should offer first. */
export function defaultMode(modes: CompetenceBindMode[]): CompetenceBindMode {
  return modes.includes('field') ? 'field' : (modes[0] ?? 'field')
}

/**
 * Trim the evidence boxes and drop the empty ones, returning null when the
 * whole form was left alone.
 *
 * An untouched box must arrive as absent, not as `''`. The two are not the same
 * claim: absent says nobody recorded the serial, and `''` says someone recorded
 * that it is blank. The server normalises this too — doing it here as well
 * keeps the request honest rather than relying on the far end to tidy up.
 */
export function normaliseEvidence(
  evidence: Record<string, string | null | undefined>,
): Record<string, string> | null {
  const cleaned: Record<string, string> = {}
  for (const [key, value] of Object.entries(evidence)) {
    const trimmed = (value ?? '').trim()
    if (trimmed !== '') cleaned[key] = trimmed
  }
  return Object.keys(cleaned).length === 0 ? null : cleaned
}
