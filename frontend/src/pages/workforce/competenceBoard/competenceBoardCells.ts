/**
 * Pure cell model for the Plant / People competence board (CB-UI-1).
 *
 * ADR-0026 separates *issued* from *demonstrated*, and the whole point of this
 * module is that the separation survives contact with a colour. Three rules
 * come out of that and are enforced by the tests beside this file:
 *
 * 1. A characteristic with no source record is absent from `cells`. Absent is
 *    "PAMS/Atlas says nothing here" — it is not a failure and must not be
 *    painted like one.
 * 2. Issued-but-never-demonstrated is the normal state of a plant board with an
 *    empty `competence_assessment_binds` table, which is exactly where the
 *    product is until CB-UI-2. Greying it out would report the absence of a
 *    QGP assessment as a competence problem in PAMS, which it is not.
 * 3. Only a QGP assessment that actually recorded a fail earns the fail tone.
 *
 * Dates are compared as `YYYY-MM-DD` strings against a locally-formatted today.
 * String comparison is exact for that format and cannot drift a day across a
 * timezone the way `new Date('2026-09-03') < new Date()` can.
 */
import type { CompetenceBoardCell } from '../../../api/competenceBoardClient'

export type PlantCellState = 'no_record' | 'issued' | 'demonstrated_pass' | 'demonstrated_fail'

export type PeopleCellState = 'no_record' | 'passed' | 'passed_expired' | 'expiry_without_pass'

/**
 * Tone per state. `no_record` and `issued` deliberately carry no fill and no
 * destructive colour — see rules 1 and 2 above.
 */
export const PLANT_CELL_TONE: Record<PlantCellState, string> = {
  no_record: 'border border-dashed border-border bg-transparent',
  issued: 'border border-primary/60 bg-primary/25',
  demonstrated_pass: 'border border-success bg-success',
  demonstrated_fail: 'border border-destructive bg-destructive',
}

export const PEOPLE_CELL_TONE: Record<PeopleCellState, string> = {
  no_record: 'border border-dashed border-border bg-transparent',
  passed: 'border border-success bg-success',
  passed_expired: 'border border-warning bg-warning/40',
  expiry_without_pass: 'border border-warning bg-transparent',
}

export function todayIso(now: Date = new Date()): string {
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function isPast(isoDate: string | null | undefined, today: string): boolean {
  if (!isoDate) return false
  return isoDate.slice(0, 10) < today
}

function formatDate(isoDate: string | null | undefined): string {
  return (isoDate ?? '').slice(0, 10)
}

export function plantCellState(
  cell: CompetenceBoardCell | undefined,
  today: string = todayIso(),
): PlantCellState {
  if (!cell) return 'no_record'
  if (cell.demonstrated === 'fail') return 'demonstrated_fail'
  if (cell.demonstrated === 'pass') {
    // A lapsed demonstration is not a fail. It falls back to what PAMS still
    // says, and the summary explains that the demonstration expired.
    return isPast(cell.demonstrated_expires_on, today) ? 'issued' : 'demonstrated_pass'
  }
  return cell.issued ? 'issued' : 'no_record'
}

export function peopleCellState(
  cell: CompetenceBoardCell | undefined,
  today: string = todayIso(),
): PeopleCellState {
  if (!cell) return 'no_record'
  if (!cell.issued) {
    // The Atlas import keeps a row that carries an expiry with no pass date.
    // That is a defect in the source record, not a competence verdict.
    return cell.expires_on ? 'expiry_without_pass' : 'no_record'
  }
  return isPast(cell.expires_on, today) ? 'passed_expired' : 'passed'
}

/** Full sentence read out to screen readers and shown on hover. */
export function plantCellSummary(
  columnLabel: string,
  cell: CompetenceBoardCell | undefined,
  today: string = todayIso(),
): string {
  const state = plantCellState(cell, today)
  const parts: string[] = [columnLabel]
  switch (state) {
    case 'no_record':
      parts.push('no PAMS record')
      break
    case 'issued':
      parts.push('issued in PAMS, not demonstrated in QGP')
      if (cell?.demonstrated === 'pass' && cell.demonstrated_expires_on) {
        parts.push(`previous QGP demonstration expired ${formatDate(cell.demonstrated_expires_on)}`)
      }
      break
    case 'demonstrated_pass':
      parts.push('issued in PAMS and demonstrated in QGP')
      if (cell?.assessed_at) parts.push(`assessed ${formatDate(cell.assessed_at)}`)
      if (cell?.demonstrated_expires_on) {
        parts.push(`demonstration expires ${formatDate(cell.demonstrated_expires_on)}`)
      }
      break
    case 'demonstrated_fail':
      parts.push('issued in PAMS, QGP assessment recorded a fail')
      if (cell?.assessed_at) parts.push(`assessed ${formatDate(cell.assessed_at)}`)
      break
  }
  if (cell?.thorough_exam === true) parts.push('thorough examination recorded')
  return parts.join(' — ')
}

export function peopleCellSummary(
  columnLabel: string,
  cell: CompetenceBoardCell | undefined,
  today: string = todayIso(),
): string {
  const state = peopleCellState(cell, today)
  const parts: string[] = [columnLabel]
  switch (state) {
    case 'no_record':
      parts.push('no Atlas record')
      break
    case 'passed':
      parts.push(`passed ${formatDate(cell?.passed_on) || 'on an unrecorded date'}`)
      if (cell?.expires_on) parts.push(`expires ${formatDate(cell.expires_on)}`)
      break
    case 'passed_expired':
      parts.push(`passed ${formatDate(cell?.passed_on) || 'on an unrecorded date'}`)
      parts.push(`expired ${formatDate(cell?.expires_on)}`)
      break
    case 'expiry_without_pass':
      parts.push(`Atlas holds an expiry of ${formatDate(cell?.expires_on)} with no pass date`)
      break
  }
  return parts.join(' — ')
}

/**
 * Axios-shaped status without depending on `axios.isAxiosError`, so a caller
 * that has mocked the client module still gets the 404 branch rather than the
 * generic error branch.
 */
export function apiErrorStatus(error: unknown): number | null {
  if (!error || typeof error !== 'object') return null
  const response = (error as { response?: unknown }).response
  if (!response || typeof response !== 'object') return null
  const status = (response as { status?: unknown }).status
  return typeof status === 'number' ? status : null
}
