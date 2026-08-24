/** Status helpers for Compliance Schedule — never use "Expired". */

import type { ComplianceStatus } from '../api/complianceScheduleClient'

export function statusLabel(status: ComplianceStatus | null | undefined): string {
  switch (status) {
    case 'current':
      return 'Current'
    case 'due_soon':
      return 'Due soon'
    case 'overdue':
      return 'Overdue'
    default:
      return '—'
  }
}

export function statusChipClass(status: ComplianceStatus | null | undefined): string {
  switch (status) {
    case 'current':
      return 'bg-emerald-500/10 text-emerald-700'
    case 'due_soon':
      return 'bg-amber-500/10 text-amber-800'
    case 'overdue':
      return 'bg-red-500/10 text-red-700'
    default:
      return 'bg-muted text-muted-foreground'
  }
}

/** Who an obligation belongs to, as far as this page can tell without a user lookup. */
export type Ownership = 'you' | 'other' | 'unassigned'

/**
 * An unowned obligation is reported as such rather than glossed over: it is the
 * case where reminders fall back to the admin role, and where they reach nobody
 * at all if no one holds it.
 *
 * A signed-out or unidentifiable caller yields 'other', never 'you' — the page
 * must not claim an obligation is yours when it cannot tell who you are.
 */
export function ownershipOf(
  ownerId: number | null | undefined,
  currentUserId: number | null,
): Ownership {
  if (ownerId === null || ownerId === undefined) return 'unassigned'
  return currentUserId !== null && ownerId === currentUserId ? 'you' : 'other'
}

/**
 * Human-readable owner line for the register / detail / edit hint.
 *
 * When the API has not yet populated ``owner_name`` (Wave-1 id-only responses,
 * or a soft-deleted / inactive / cross-tenant id), fall back honestly rather
 * than inventing a blank.
 */
export function formatOwnershipLabel(
  ownership: Ownership,
  ownerName?: string | null,
  labels: {
    you: string
    other: string
    unassigned: string
    youNamed?: (name: string) => string
  } = {
    you: 'Owned by you',
    other: 'Owned by someone else',
    unassigned: 'Unassigned',
  },
): string {
  const name = typeof ownerName === 'string' ? ownerName.trim() : ''
  if (ownership === 'unassigned') return labels.unassigned
  if (ownership === 'you') {
    if (name) return (labels.youNamed ?? ((n) => `${n} (you)`))(name)
    return labels.you
  }
  return name || labels.other
}

/**
 * How often the obligation recurs.
 *
 * When both intervals are set the scheduler adds them — months first, then days
 * (`compute_next_due` in compliance_schedule_policy.py) — so both are reported.
 * Picking one and dropping the other would understate the real interval.
 *
 * Returns null when no interval is recorded, so callers can distinguish "does
 * not recur on a fixed interval" from a frequency of zero.
 */
export function frequencyLabel(
  months: number | null | undefined,
  days: number | null | undefined,
): string | null {
  const m = typeof months === 'number' && months > 0 ? months : null
  const d = typeof days === 'number' && days > 0 ? days : null
  if (m === null && d === null) return null

  const parts: string[] = []
  if (m !== null) parts.push(m === 1 ? '1 month' : `${m} months`)
  if (d !== null) parts.push(d === 1 ? '1 day' : `${d} days`)
  return `Every ${parts.join(' and ')}`
}

export type ComplianceAnchor = 'completion' | 'schedule'

/**
 * The raw anchor values are `schedule` and `completion`, which say nothing to
 * the person reading the record about which date the next one is measured from.
 */
export function anchorLabel(anchor: ComplianceAnchor | null | undefined): string {
  switch (anchor) {
    case 'completion':
      return 'From completion'
    case 'schedule':
      return 'Fixed schedule'
    default:
      return '—'
  }
}

export function anchorHint(anchor: ComplianceAnchor | null | undefined): string | null {
  switch (anchor) {
    case 'completion':
      return 'The next date is measured from the day the work is done, so completing late pushes the whole schedule back.'
    case 'schedule':
      return 'The next date is measured from the current due date, so the anniversary holds even if the work is done late.'
    default:
      return null
  }
}

export function deriveStatusFromDue(
  nextDue: string | null | undefined,
  now: Date = new Date(),
  dueSoonDays = 30,
): ComplianceStatus | null {
  if (!nextDue) return null
  const due = new Date(nextDue)
  if (Number.isNaN(due.getTime())) return null
  const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
  const dueDay = new Date(Date.UTC(due.getUTCFullYear(), due.getUTCMonth(), due.getUTCDate()))
  const delta = Math.round((dueDay.getTime() - today.getTime()) / 86_400_000)
  if (delta < 0) return 'overdue'
  if (delta <= dueSoonDays) return 'due_soon'
  return 'current'
}
