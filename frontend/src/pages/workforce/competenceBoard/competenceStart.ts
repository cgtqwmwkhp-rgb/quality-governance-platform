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

/**
 * Where a block is already explained on screen.
 *
 * `context` means surrounding copy states it once already — the Plant/People tab
 * for a wrong-family block, the column header's "No family template yet" for an
 * unbound characteristic, the row's "No QGP employee record" badge for an
 * unlinked person, and the notice above the table for an assessor who cannot
 * assess anything. Repeating those on every square would read the same paragraph
 * out hundreds of times to a screen-reader user without adding a fact.
 *
 * `cell` means this square is the only place the reason appears, because it is
 * true of this row or this column and not of the grid — you cannot assess
 * yourself (your row only), or PAMS has not issued you this characteristic (that
 * column only). Those must be announced or the square is silently inert.
 */
export type StartBlockScope = 'context' | 'cell'

export type CellStartability =
  | { status: 'startable'; modes: CompetenceBindMode[] }
  | { status: 'blocked'; reason: string; scope: StartBlockScope }

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
  if (family !== 'pams') return { status: 'blocked', reason: NOT_PLANT_FAMILY, scope: 'context' }

  const modes = boundModes(column)
  if (modes.length === 0) return { status: 'blocked', reason: NO_FAMILY_TEMPLATE, scope: 'context' }

  if (!person.mapped || person.engineer_id == null) {
    return { status: 'blocked', reason: PERSON_NOT_LINKED, scope: 'context' }
  }

  // An absent assessor block is treated as "cannot prove it", not as "allowed".
  // A server that has not been upgraded must not silently open the gate. Scoped
  // to the cell because an old server sends no notice above the table either, so
  // the square would otherwise be the only place this could be said, and it says
  // nothing.
  if (!assessor) {
    return { status: 'blocked', reason: assessorNotIssued(column.label), scope: 'cell' }
  }
  if (assessor.blocked_reason) {
    return { status: 'blocked', reason: assessor.blocked_reason, scope: 'context' }
  }
  if (assessor.engineer_id == null) {
    return { status: 'blocked', reason: assessorNotIssued(column.label), scope: 'cell' }
  }
  if (assessor.engineer_id === person.engineer_id) {
    return { status: 'blocked', reason: CANNOT_ASSESS_SELF, scope: 'cell' }
  }

  const issued = Array.isArray(assessor.issued_characteristic_keys)
    ? assessor.issued_characteristic_keys
    : []
  if (!issued.includes(column.key)) {
    return { status: 'blocked', reason: assessorNotIssued(column.label), scope: 'cell' }
  }

  return { status: 'startable', modes }
}

/**
 * The startability half of a cell's screen-reader summary: an action when it can
 * be started, otherwise the reason it cannot.
 */
export function startabilitySummary(startability: CellStartability): string {
  if (startability.status === 'startable') {
    return `can start ${startability.modes.join(' or ')} assessment`
  }
  return startability.reason
}

/**
 * The cell's full screen-reader sentence: its PAMS state, plus its startability
 * where that adds a fact the surrounding copy does not already state.
 *
 * A square that is a button for one person and inert for another with no
 * explanation is the thing this slice must not ship — so `cell`-scoped blocks
 * are always announced. `context`-scoped ones are left to the copy that already
 * carries them, because reading an identical paragraph on every square of a
 * twenty-column grid buries the state the square exists to convey.
 */
export function cellAnnouncement(stateSentence: string, startability: CellStartability): string {
  if (startability.status === 'blocked' && startability.scope === 'context') {
    return stateSentence
  }
  return `${stateSentence} — ${startabilitySummary(startability)}`
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
