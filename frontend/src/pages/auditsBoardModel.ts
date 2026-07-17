/**
 * AUD-W-01 / Round 3 Audits board contract.
 * Preferred model: 3 work lanes + program filter chips (not equal 4-col status board).
 * Shipped on main via AUD-W-W1 (#1059); this module locks the grouping for tests.
 */
import type { AuditRun } from '../api/client'
import {
  isAchillesUvdbAssuranceAudit,
  isCustomerAssuranceAudit,
} from '../components/assuranceHubHelpers'

export type AuditProgram = 'internal' | 'uvdb' | 'planet_mark' | 'customer'

export const BOARD_WORK_LANES = [
  {
    id: 'do_now',
    label: 'Do now',
    labelKey: 'audits.board.lane.do_now',
    statuses: ['scheduled', 'in_progress'] as const,
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
  const extType = (
    (audit as AuditRun & { external_audit_type?: string }).external_audit_type || ''
  ).toLowerCase()
  const scheme = (audit.assurance_scheme || '').trim().toLowerCase()
  if (extType === 'planet_mark' || scheme.includes('planet mark')) return 'planet_mark'
  return 'internal'
}

export function getAuditsForLaneStatuses(
  audits: AuditRun[],
  statuses: readonly string[],
): AuditRun[] {
  return audits.filter((audit) => statuses.includes(audit.status))
}
