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
