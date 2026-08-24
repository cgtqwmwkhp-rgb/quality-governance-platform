/**
 * AUD-W-01 / A4 Audits board contract.
 * Four named work lanes: Planned / Fieldwork / Review / Closed.
 * Not four equal status columns named scheduled / in_progress / pending_review / completed.
 * Program filter chips stay. Do now KPI remains the executable set (Planned + Fieldwork).
 */
import type { AuditRun } from '../api/client'
import {
  isAchillesUvdbAssuranceAudit,
  isCustomerAssuranceAudit,
  isPlanetMarkAssuranceAudit,
} from '../components/assuranceHubHelpers'

export type AuditProgram = 'internal' | 'uvdb' | 'planet_mark' | 'customer'

export const BOARD_WORK_LANES = [
  {
    id: 'planned',
    label: 'Planned',
    labelKey: 'audits.board.lane.planned',
    statuses: ['scheduled'] as const,
    variant: 'default' as const,
  },
  {
    id: 'fieldwork',
    label: 'Fieldwork',
    labelKey: 'audits.board.lane.fieldwork',
    statuses: ['in_progress'] as const,
    variant: 'warning' as const,
  },
  {
    id: 'review',
    label: 'Needs review',
    labelKey: 'audits.board.lane.review',
    statuses: ['pending_review'] as const,
    variant: 'default' as const,
  },
  {
    id: 'closed',
    label: 'Closed',
    labelKey: 'audits.board.lane.closed',
    statuses: ['completed'] as const,
    variant: 'success' as const,
  },
] as const

export type BoardWorkLaneId = (typeof BOARD_WORK_LANES)[number]['id']

export const BOARD_STATUS_IDS = new Set<string>(
  BOARD_WORK_LANES.flatMap((lane) => lane.statuses),
)

export const PROGRAM_FILTER_CHIPS: Array<{
  id: AuditProgram
  label: string
  labelKey: string
}> = [
  { id: 'internal', label: 'Internal', labelKey: 'audits.board.program.internal' },
  { id: 'uvdb', label: 'Achilles UVDB', labelKey: 'audits.board.program.uvdb' },
  { id: 'planet_mark', label: 'Planet Mark', labelKey: 'audits.board.program.planet_mark' },
  { id: 'customer', label: 'Customer', labelKey: 'audits.board.program.customer' },
]

export function classifyAuditProgram(audit: AuditRun): AuditProgram {
  if (isCustomerAssuranceAudit(audit)) return 'customer'
  if (isAchillesUvdbAssuranceAudit(audit)) return 'uvdb'
  if (isPlanetMarkAssuranceAudit(audit)) return 'planet_mark'
  return 'internal'
}

export type AuditsListDensity = 'comfort' | 'compact'

export const AUDITS_LIST_DENSITY_STORAGE_KEY = 'qgp.audits.listDensity'
export const AUDITS_LIST_DENSITY_DEFAULT: AuditsListDensity = 'comfort'

export function parseAuditsListDensity(raw: string | null | undefined): AuditsListDensity {
  return raw === 'compact' ? 'compact' : AUDITS_LIST_DENSITY_DEFAULT
}

export function auditsListCellClass(density: AuditsListDensity): string {
  return density === 'compact' ? 'px-3 py-2' : 'px-6 py-4'
}

export function getAuditsForLaneStatuses(
  audits: AuditRun[],
  statuses: readonly string[],
): AuditRun[] {
  return audits.filter((audit) => statuses.includes(audit.status))
}

/** Executable work = Planned + Fieldwork. Hero Do now KPI still uses this set (N3). */
const DO_NOW_STATUSES: readonly string[] = BOARD_WORK_LANES.filter(
  (lane) => lane.id === 'planned' || lane.id === 'fieldwork',
).flatMap((lane) => [...lane.statuses])

export function isDoNowAuditStatus(status: string): boolean {
  return DO_NOW_STATUSES.includes(status)
}

export function countDoNowAudits(audits: readonly Pick<AuditRun, 'status'>[]): number {
  return audits.filter((audit) => isDoNowAuditStatus(audit.status)).length
}

/** A5: Closed on the board is recent work, not the archive. List keeps history. */
export const CLOSED_BOARD_WINDOW_DAYS = 30
export const CLOSED_BOARD_MAX_CARDS = 8
const CLOSED_BOARD_WINDOW_MS = CLOSED_BOARD_WINDOW_DAYS * 24 * 60 * 60 * 1000

export function closedBoardTimestampMs(audit: AuditRun): number {
  const raw = audit.completed_at || audit.scheduled_date || audit.created_at
  const parsed = Date.parse(raw)
  return Number.isFinite(parsed) ? parsed : Number.NaN
}

export type ClosedBoardPartition = {
  visible: AuditRun[]
  moreCount: number
}

/**
 * Closed lane cards: completed within the window, newest first, capped.
 * `moreCount` is closed runs in this loaded set that are not on the board.
 * It is not a tenant-wide total.
 */
export function partitionClosedForBoard(
  audits: readonly AuditRun[],
  nowMs: number = Date.now(),
): ClosedBoardPartition {
  const closed = audits.filter((audit) => audit.status === 'completed')
  const inWindow = closed
    .filter((audit) => {
      const ts = closedBoardTimestampMs(audit)
      return Number.isFinite(ts) && nowMs - ts <= CLOSED_BOARD_WINDOW_MS
    })
    .sort((a, b) => closedBoardTimestampMs(b) - closedBoardTimestampMs(a))
  const visible = inWindow.slice(0, CLOSED_BOARD_MAX_CARDS)
  return {
    visible,
    moreCount: closed.length - visible.length,
  }
}

/** A2: a stored 0% with no denominator is missing, not a scored result. */
export function auditRunIsScored(
  audit: Pick<AuditRun, 'score_percentage' | 'max_score'>,
): boolean {
  if (audit.score_percentage == null) return false
  if (audit.max_score != null && audit.max_score <= 0) return false
  if (audit.max_score == null && audit.score_percentage === 0) return false
  return true
}

export function formatAuditsAverageScore(audits: readonly AuditRun[]): {
  value: string
  caption: string | null
} {
  const scored = audits.filter(auditRunIsScored)
  if (scored.length === 0) {
    return { value: '—', caption: 'Not scored in this view' }
  }
  const avg =
    scored.reduce((acc, audit) => acc + (audit.score_percentage ?? 0), 0) / scored.length
  return { value: `${avg.toFixed(0)}%`, caption: null }
}
