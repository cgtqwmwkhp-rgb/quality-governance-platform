/**
 * Pure row model for the assessment bind screen (CB-UI-2).
 *
 * The screen maps published QGP templates onto PAMS characteristics. What it
 * must not do is let "QGP has not mapped this characteristic yet" look like
 * "this characteristic is a problem". CB-UI-1 removed exactly that defect from
 * the board — `not_assessed` was painted `bg-muted-foreground/40`, the same
 * visual weight as `failed` — and an admin screen that greys out its unmapped
 * rows would put it straight back, one screen upstream.
 *
 * So three rules, asserted by the tests beside this file:
 *
 * 1. Every characteristic in the snapshot gets a row, bound or not. Filtering
 *    unbound ones out would hide the work rather than report it.
 * 2. The unbound tone carries no fill and no destructive colour. An unbound
 *    characteristic is a gap in QGP's mapping, not in anyone's competence.
 * 3. A bind whose characteristic has left the snapshot is still shown, flagged
 *    as unmatched. Dropping it would leave a live row in the database with no
 *    surface to remove it from.
 */
import type {
  CompetenceAssessmentBind,
  CompetenceBindMode,
  CompetenceCharacteristic,
} from '../../../api/competenceBindClient'

export type BindCellState = 'bound' | 'unbound'

/**
 * Tone per state. `unbound` deliberately carries no fill and no destructive
 * colour — see rule 2 above. It is the same visual language CB-UI-1 uses for
 * "the source says nothing here".
 */
export const BIND_CELL_TONE: Record<BindCellState, string> = {
  bound: 'border border-success bg-success/15 text-foreground',
  unbound: 'border border-dashed border-border bg-transparent text-muted-foreground',
}

export const MODE_LABEL: Record<CompetenceBindMode, string> = {
  field: 'Field assessment',
  induction: 'Induction',
}

export type CharacteristicBindRow = {
  key: string
  label: string
  /** False when only a bind mentions this characteristic — see rule 3. */
  inSnapshot: boolean
  field: CompetenceAssessmentBind | null
  induction: CompetenceAssessmentBind | null
}

function bindFor(
  binds: CompetenceAssessmentBind[],
  key: string,
  mode: CompetenceBindMode,
): CompetenceAssessmentBind | null {
  return binds.find((bind) => bind.characteristic_key === key && bind.mode === mode) ?? null
}

/**
 * One row per characteristic: those in the snapshot first (alphabetical), then
 * any bound characteristic the snapshot no longer holds.
 */
export function buildBindRows(
  characteristics: CompetenceCharacteristic[],
  binds: CompetenceAssessmentBind[],
): CharacteristicBindRow[] {
  const safeCharacteristics = Array.isArray(characteristics) ? characteristics : []
  const safeBinds = Array.isArray(binds) ? binds : []

  const known = new Map<string, string>()
  for (const entry of safeCharacteristics) {
    if (entry?.key) known.set(entry.key, entry.label || entry.key)
  }

  const orphans = new Set<string>()
  for (const bind of safeBinds) {
    if (bind?.characteristic_key && !known.has(bind.characteristic_key)) {
      orphans.add(bind.characteristic_key)
    }
  }

  const build = (key: string, label: string, inSnapshot: boolean): CharacteristicBindRow => ({
    key,
    label,
    inSnapshot,
    field: bindFor(safeBinds, key, 'field'),
    induction: bindFor(safeBinds, key, 'induction'),
  })

  return [
    ...[...known.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([key, label]) => build(key, label, true)),
    ...[...orphans].sort((a, b) => a.localeCompare(b)).map((key) => build(key, key, false)),
  ]
}

export function bindCellState(bind: CompetenceAssessmentBind | null): BindCellState {
  return bind ? 'bound' : 'unbound'
}

/** Plain English for the interval. Absent is never rendered as "never expires". */
export function intervalSummary(bind: CompetenceAssessmentBind | null): string {
  if (!bind) return ''
  if (bind.interval_days == null) {
    return 'no interval on this bind — a pass expires on the competency requirement instead'
  }
  return bind.interval_days === 1 ? 'reassess every day' : `reassess every ${bind.interval_days} days`
}

/** Full sentence read out to screen readers and shown on hover. */
export function bindCellSummary(
  row: CharacteristicBindRow,
  mode: CompetenceBindMode,
  templateName: (templateId: number) => string,
): string {
  const bind = mode === 'field' ? row.field : row.induction
  const parts: string[] = [`${row.label} — ${MODE_LABEL[mode].toLowerCase()}`]
  if (!bind) {
    parts.push('no template bound, so QGP records no demonstration for this column')
    return parts.join(' — ')
  }
  parts.push(`bound to ${templateName(bind.template_id)}`)
  parts.push(intervalSummary(bind))
  return parts.join(' — ')
}

/**
 * Axios-shaped status without depending on `axios.isAxiosError`, so a caller
 * that has mocked the client module still gets the 404 branch.
 */
export function apiErrorStatus(error: unknown): number | null {
  if (!error || typeof error !== 'object') return null
  const response = (error as { response?: unknown }).response
  if (!response || typeof response !== 'object') return null
  const status = (response as { status?: unknown }).status
  return typeof status === 'number' ? status : null
}
